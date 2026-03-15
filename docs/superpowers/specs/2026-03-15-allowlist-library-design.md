# AllowList Security Library — Design Specification

**Date:** 2026-03-15
**Status:** Approved
**Author:** Design session via Claude Code / Superpowers brainstorming

---

## Overview

A multi-module Java library that enables Spring Security method-level access control via a named allow-list annotation. Controller methods are annotated with `@AllowList("list-name")`. The list is configured in `application.yml` (compatible with Spring Cloud Config) and matched against the `sub` claim of an incoming JWT bearer token, as resolved by Spring Security.

The library targets Spring Boot 3.x and Spring Boot 4.x. It is intended for use across up to 100 internal services, each potentially on a different Boot minor version.

---

## Goals

- Annotation-driven allow-list enforcement at the controller method level
- Named lists configured via Spring `@ConfigurationProperties`, compatible with Spring Cloud Config refresh
- No JWT parsing in the library — requires Spring Security's JWT resource server to be configured (either by the service or optionally by the library's starter)
- Stable builds across all Spring Boot 3.x minor releases and Boot 4.x
- Maximum decoupling: pure Java core with no Spring dependency; Spring-specific code isolated to thin adapter layers
- Zero-friction consumer experience: import BOM, add one starter dependency, annotate methods

## Non-Goals (current version)

- Database-backed allow-lists (the `AllowListRegistry` interface is the extension point for this later)
- `anyOf` / `allOf` multi-list annotation semantics (documented as future work — see Section 8)
- Compile-time annotation validation (startup validation is included; compile-time is future work)

---

## Module Structure

```
allowlist-parent                          (aggregator POM / build config)
├── allowlist-bom                         (Bill of Materials)
├── allowlist-core                        (pure Java, zero dependencies)
├── allowlist-spring-security             (Spring Security integration)
├── allowlist-spring-config               (@ConfigurationProperties + refresh)
├── allowlist-spring-boot-starter-boot3   (Boot 3.x autoconfiguration)
└── allowlist-spring-boot-starter-boot4   (Boot 4.x autoconfiguration)
```

### Dependency graph

```
[boot3-starter] ──► [spring-config] ──► [spring-security] ──► [core]
[boot4-starter] ──► [spring-config] ──► [spring-security] ──► [core]
```

### Module responsibilities

| Module | Spring deps | Owns |
|---|---|---|
| `allowlist-core` | none | `@AllowList`, `AllowListRegistry`, `MapAllowListRegistry`, `SubjectExtractor` |
| `allowlist-spring-security` | spring-security-core (compileOnly) | `AllowListAuthorizationManager`, `AllowListMethodSecurityConfiguration`, `AllowListNotFoundException` |
| `allowlist-spring-config` | spring-boot (compileOnly) | `AllowListProperties`, `AllowListRegistryFactory`, `AllowListSpringConfigConfiguration`, startup validator |
| `allowlist-spring-boot-starter-boot3` | spring-boot-autoconfigure (compileOnly) | `AllowListBoot3AutoConfiguration`, optional JWT `SecurityFilterChain` |
| `allowlist-spring-boot-starter-boot4` | spring-boot-autoconfigure (compileOnly) | `AllowListBoot4AutoConfiguration`, optional JWT `SecurityFilterChain` |
| `allowlist-bom` | — | Version declarations for all of the above |

---

## Section 1: `allowlist-core` — Pure Java API

Zero dependencies. All contracts the rest of the library is built on live here. Testable with plain JUnit — no Spring test context needed.

### `@AllowList`

```java
package com.example.allowlist.core;

import java.lang.annotation.*;

@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface AllowList {
    /**
     * The name of the allow-list to check against.
     * Must match a key under allowlist.lists in configuration.
     */
    String value();
}
```

Plain Java annotation. No Spring imports.

### `AllowListRegistry`

```java
package com.example.allowlist.core;

public interface AllowListRegistry {
    /**
     * Returns true if subject appears in the named list.
     * Returns false if the list does not exist or subject is absent.
     */
    boolean isAllowed(String listName, String subject);

    /**
     * Returns true if the named list is registered (even if empty).
     */
    boolean listExists(String listName);
}
```

The primary extension point. Alternative implementations (database-backed, remote-fetched) implement this interface.

### `MapAllowListRegistry`

```java
package com.example.allowlist.core;

import java.util.*;

public class MapAllowListRegistry implements AllowListRegistry {

    private final Map<String, Set<String>> lists;

    public MapAllowListRegistry(Map<String, ? extends Collection<String>> lists) {
        Map<String, Set<String>> copy = new HashMap<>();
        lists.forEach((k, v) -> copy.put(k, Set.copyOf(v)));
        this.lists = Collections.unmodifiableMap(copy);
    }

    @Override
    public boolean isAllowed(String listName, String subject) {
        return lists.getOrDefault(listName, Set.of()).contains(subject);
    }

    @Override
    public boolean listExists(String listName) {
        return lists.containsKey(listName);
    }
}
```

Immutable snapshot constructed at startup (or on refresh). Subject lookup is O(1) via `HashSet`.

### `SubjectExtractor`

```java
package com.example.allowlist.core;

public interface SubjectExtractor<T> {
    String extract(T source);
}
```

Not used in the default flow (subject comes from `Authentication.getName()`). Included as the extension point for custom extraction (e.g. non-standard claim name). Kept in core so it carries no Spring dependency.

---

## Section 2: `allowlist-spring-security` — Spring Security Integration

All Spring deps declared `compileOnly` (Gradle) / `provided` (Maven). No Spring JARs shipped in the artifact.

Uses Spring Security 6's `AuthorizationManager<MethodInvocation>` API, introduced in Security 6.0 as the replacement for `AccessDecisionManager`. Expected stable through Security 7.

### `AllowListAuthorizationManager`

```java
package com.example.allowlist.spring.security;

import com.example.allowlist.core.*;
import org.aopalliance.intercept.MethodInvocation;
import org.springframework.security.authorization.*;
import org.springframework.security.core.Authentication;
import java.util.function.Supplier;

public class AllowListAuthorizationManager
        implements AuthorizationManager<MethodInvocation> {

    private final AllowListRegistry registry;

    public AllowListAuthorizationManager(AllowListRegistry registry) {
        this.registry = registry;
    }

    @Override
    public AuthorizationDecision check(
            Supplier<Authentication> authSupplier,
            MethodInvocation invocation) {

        AllowList annotation = findAnnotation(invocation);
        if (annotation == null) {
            return new AuthorizationDecision(true); // not our concern
        }

        String listName = annotation.value();
        String subject  = authSupplier.get().getName();

        if (!registry.listExists(listName)) {
            // misconfiguration — fail closed with a clear message
            throw new AllowListNotFoundException(
                "No allow-list configured with name: " + listName);
        }

        return new AuthorizationDecision(registry.isAllowed(listName, subject));
    }

    private AllowList findAnnotation(MethodInvocation invocation) {
        AllowList ann = invocation.getMethod().getAnnotation(AllowList.class);
        if (ann != null) return ann;
        return invocation.getMethod()
                         .getDeclaringClass()
                         .getAnnotation(AllowList.class);
    }
}
```

**Design decisions:**
- Unknown list name → throws `AllowListNotFoundException` (fail closed). A missing list is a misconfiguration, not a normal access denial. Silent denial would hide wiring errors.
- Missing annotation on method → pass through (`true`). The interceptor is broad-spectrum; non-annotated methods are not this library's concern.

### `AllowListNotFoundException`

```java
package com.example.allowlist.spring.security;

public class AllowListNotFoundException extends RuntimeException {
    public AllowListNotFoundException(String message) {
        super(message);
    }
}
```

Pure Java exception. Spring's default exception translation maps unchecked exceptions to HTTP 500. Services can add a `@ExceptionHandler` to remap to 403 if preferred, or add a `@ControllerAdvice` globally.

### `AllowListMethodSecurityConfiguration`

```java
package com.example.allowlist.spring.security;

import com.example.allowlist.core.AllowList;
import org.springframework.aop.support.annotation.AnnotationMatchingPointcut;
import org.springframework.context.annotation.Bean;
import org.springframework.security.authorization.method.AuthorizationManagerBeforeMethodInterceptor;

public class AllowListMethodSecurityConfiguration {

    @Bean
    public AuthorizationManagerBeforeMethodInterceptor allowListMethodInterceptor(
            AllowListAuthorizationManager authorizationManager) {

        return new AuthorizationManagerBeforeMethodInterceptor(
            new AnnotationMatchingPointcut(null, AllowList.class),
            authorizationManager
        );
    }
}
```

Deliberately not a `@Configuration` class. It is imported explicitly by the starter's `@AutoConfiguration`, preventing this module from self-activating on the classpath.

---

## Section 3: `allowlist-spring-config` — Configuration Binding

### YAML configuration shape

```yaml
allowlist:
  lists:
    finance-admins:
      - alice
      - bob.smith
    super-admins:
      - charlie
    readonly-users:
      - dave
      - eve
  jwt:
    auto-configure: false   # opt-in to library-managed SecurityFilterChain
```

List keys are arbitrary names. Values are exact JWT `sub` claim strings (case-sensitive — see Issues section).

### `AllowListProperties`

```java
package com.example.allowlist.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import java.util.*;

@ConfigurationProperties(prefix = "allowlist")
public class AllowListProperties {

    private Map<String, List<String>> lists = new HashMap<>();
    private Jwt jwt = new Jwt();

    public Map<String, List<String>> getLists() { return lists; }
    public void setLists(Map<String, List<String>> lists) { this.lists = lists; }
    public Jwt getJwt() { return jwt; }
    public void setJwt(Jwt jwt) { this.jwt = jwt; }

    public static class Jwt {
        private boolean autoConfigure = false;
        public boolean isAutoConfigure() { return autoConfigure; }
        public void setAutoConfigure(boolean autoConfigure) {
            this.autoConfigure = autoConfigure;
        }
    }
}
```

No `@Component` or `@RefreshScope` here. Scope is the autoconfiguration layer's decision.

### `AllowListRegistryFactory`

```java
package com.example.allowlist.config;

import com.example.allowlist.core.*;

public class AllowListRegistryFactory {

    public static AllowListRegistry create(AllowListProperties properties) {
        return new MapAllowListRegistry(properties.getLists());
    }
}
```

Separates construction from bean declaration. Makes refresh handling explicit — when Spring Cloud Config fires a refresh, the scoped proxy re-calls this factory.

### `AllowListSpringConfigConfiguration`

```java
package com.example.allowlist.config;

import com.example.allowlist.core.AllowListRegistry;
import com.example.allowlist.spring.security.*;
import org.springframework.boot.autoconfigure.condition.*;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.*;

@Import(AllowListMethodSecurityConfiguration.class)
@EnableConfigurationProperties(AllowListProperties.class)
public class AllowListSpringConfigConfiguration {

    // Variant activated when spring-cloud-context is present (refresh-aware)
    @Bean
    @ConditionalOnMissingBean(AllowListRegistry.class)
    @ConditionalOnClass(name =
        "org.springframework.cloud.context.scope.refresh.RefreshScope")
    @org.springframework.cloud.context.config.annotation.RefreshScope
    public AllowListRegistry allowListRegistryRefreshable(AllowListProperties props) {
        return AllowListRegistryFactory.create(props);
    }

    // Variant activated when spring-cloud-context is absent (static)
    @Bean
    @ConditionalOnMissingBean(AllowListRegistry.class)
    @ConditionalOnMissingClass(
        "org.springframework.cloud.context.scope.refresh.RefreshScope")
    public AllowListRegistry allowListRegistryStatic(AllowListProperties props) {
        return AllowListRegistryFactory.create(props);
    }

    @Bean
    @ConditionalOnMissingBean
    public AllowListAuthorizationManager allowListAuthorizationManager(
            AllowListRegistry registry) {
        return new AllowListAuthorizationManager(registry);
    }
}
```

All beans are `@ConditionalOnMissingBean` — services can override any bean by declaring their own.

### Startup validator

```java
package com.example.allowlist.config;

import com.example.allowlist.core.*;
import com.example.allowlist.spring.security.AllowListNotFoundException;
import org.springframework.context.ApplicationListener;
import org.springframework.context.event.ContextRefreshedEvent;
import java.lang.reflect.Method;
import java.util.*;

public class AllowListStartupValidator
        implements ApplicationListener<ContextRefreshedEvent> {

    private final AllowListRegistry registry;

    public AllowListStartupValidator(AllowListRegistry registry) {
        this.registry = registry;
    }

    @Override
    public void onApplicationEvent(ContextRefreshedEvent event) {
        // Scan all beans for @AllowList annotated methods
        String[] beanNames = event.getApplicationContext().getBeanDefinitionNames();
        List<String> unknownLists = new ArrayList<>();

        for (String beanName : beanNames) {
            try {
                Object bean = event.getApplicationContext().getBean(beanName);
                for (Method method : bean.getClass().getMethods()) {
                    AllowList ann = method.getAnnotation(AllowList.class);
                    if (ann != null && !registry.listExists(ann.value())) {
                        unknownLists.add(
                            beanName + "#" + method.getName()
                            + " references unknown list: '" + ann.value() + "'");
                    }
                }
            } catch (Exception ignored) { /* skip uninstantiable beans */ }
        }

        if (!unknownLists.isEmpty()) {
            throw new AllowListNotFoundException(
                "AllowList configuration errors at startup:\n"
                + String.join("\n", unknownLists));
        }
    }
}
```

Fails fast at application startup rather than on first request. Surfaces typos in list names before any traffic reaches the service.

---

## Section 4: Boot Starters — Autoconfiguration

### `allowlist-spring-boot-starter-boot3`

```java
package com.example.allowlist.boot3;

import com.example.allowlist.config.AllowListSpringConfigConfiguration;
import com.example.allowlist.config.AllowListStartupValidator;
import com.example.allowlist.core.AllowListRegistry;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.*;
import org.springframework.context.annotation.*;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.Customizer;
import org.springframework.security.web.SecurityFilterChain;

@AutoConfiguration
@ConditionalOnClass(name = {
    "org.springframework.security.web.SecurityFilterChain",
    "com.example.allowlist.core.AllowListRegistry"
})
@Import(AllowListSpringConfigConfiguration.class)
public class AllowListBoot3AutoConfiguration {

    @Bean
    public AllowListStartupValidator allowListStartupValidator(
            AllowListRegistry registry) {
        return new AllowListStartupValidator(registry);
    }

    @Bean
    @ConditionalOnMissingBean(SecurityFilterChain.class)
    @ConditionalOnProperty(
        prefix = "allowlist.jwt",
        name = "auto-configure",
        havingValue = "true",
        matchIfMissing = false)
    public SecurityFilterChain allowListJwtFilterChain(HttpSecurity http)
            throws Exception {
        return http
            .authorizeHttpRequests(auth -> auth.anyRequest().authenticated())
            .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
            .build();
    }
}
```

Registered via `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`:

```
com.example.allowlist.boot3.AllowListBoot3AutoConfiguration
```

### `allowlist-spring-boot-starter-boot4`

Structurally identical. A separate class and `AutoConfiguration.imports` entry. Any Boot 4 / Security 7 DSL divergence is isolated here. Initially ships as a thin duplicate; diverges only if Boot 4 requires it.

### `allowlist.jwt.auto-configure` behaviour

| Value | Behaviour |
|---|---|
| absent or `false` | Library registers `@AllowList` enforcement only. Service owns its `SecurityFilterChain`. |
| `true` | Library also registers a default JWT-validating `SecurityFilterChain`. Service provides `spring.security.oauth2.resourceserver.jwt.issuer-uri` only. |

---

## Section 5: BOM and Versioning

### `allowlist-bom`

```xml
<project>
  <groupId>com.example</groupId>
  <artifactId>allowlist-bom</artifactId>
  <version>1.0.0</version>
  <packaging>pom</packaging>
  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>com.example</groupId><artifactId>allowlist-core</artifactId>
        <version>1.0.0</version>
      </dependency>
      <dependency>
        <groupId>com.example</groupId><artifactId>allowlist-spring-security</artifactId>
        <version>1.0.0</version>
      </dependency>
      <dependency>
        <groupId>com.example</groupId><artifactId>allowlist-spring-config</artifactId>
        <version>1.0.0</version>
      </dependency>
      <dependency>
        <groupId>com.example</groupId><artifactId>allowlist-spring-boot-starter-boot3</artifactId>
        <version>1.0.0</version>
      </dependency>
      <dependency>
        <groupId>com.example</groupId><artifactId>allowlist-spring-boot-starter-boot4</artifactId>
        <version>1.0.0</version>
      </dependency>
    </dependencies>
  </dependencyManagement>
</project>
```

### Version trains

| Library version | Targets | Status |
|---|---|---|
| `1.x` | Boot 3.x, Security 6.x | Current — actively maintained |
| `2.x` | Boot 4.x, Security 7.x | Future — introduced when Boot 4 GA ships |

Both trains share source for `core`, `spring-security`, `spring-config`. They diverge only in the starter modules when required.

### `allowlist-parent` compile baseline

```xml
<properties>
  <!-- Compile against minimum supported versions -->
  <spring-security.version>6.0.0</spring-security.version>
  <spring-boot.version>3.0.0</spring-boot.version>
  <java.version>17</java.version>
</properties>
<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-dependencies</artifactId>
      <version>${spring-boot.version}</version>
      <type>pom</type>
      <scope>import</scope>
    </dependency>
  </dependencies>
</dependencyManagement>
```

### CI compatibility matrix

```yaml
# .github/workflows/compatibility.yml
strategy:
  matrix:
    spring-boot-version:
      - "3.0.13"
      - "3.1.12"
      - "3.2.10"
      - "3.3.5"
      - "3.4.1"
```

Each matrix job overrides `spring-boot.version` at test time. Compile target remains `3.0.0`.

---

## Section 6: Gradle Notes

Gradle is a fully supported build tool. The following shows the Gradle equivalents for key patterns.

### Declaring Spring deps as `compileOnly` (the critical pattern)

```kotlin
// allowlist-spring-security/build.gradle.kts
dependencies {
    api(project(":allowlist-core"))

    // Spring deps — compile against but do NOT ship in artifact
    compileOnly("org.springframework.security:spring-security-core")
    compileOnly("org.springframework.security:spring-security-config")

    // Versions come from the Spring Boot BOM imported in the root build
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.springframework.security:spring-security-test")
}
```

```kotlin
// allowlist-spring-config/build.gradle.kts
dependencies {
    api(project(":allowlist-spring-security"))

    compileOnly("org.springframework.boot:spring-boot-autoconfigure")
    compileOnly("org.springframework.boot:spring-boot-starter")
    // Optional: spring-cloud-context for @RefreshScope variant
    compileOnly("org.springframework.cloud:spring-cloud-context")
}
```

### Root `build.gradle.kts` with Spring Boot BOM import

```kotlin
// root build.gradle.kts
plugins {
    java
    `java-library`
}

allprojects {
    group = "com.example"
    version = "1.0.0"

    repositories {
        mavenCentral()
    }
}

subprojects {
    apply(plugin = "java-library")

    java {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    dependencyManagement {
        // import Spring Boot BOM to control all Spring transitive versions
        imports {
            mavenBom("org.springframework.boot:spring-boot-dependencies:3.0.0")
        }
    }
}
```

> Note: `dependencyManagement {}` requires the `io.spring.dependency-management` plugin.
> Alternative (Gradle-native): use `platform("org.springframework.boot:spring-boot-dependencies:3.0.0")` as a `compileOnly platform(...)` dependency.

### BOM consumption in a service (Gradle)

```kotlin
// consuming service build.gradle.kts
dependencies {
    // Import the allowlist BOM
    implementation(platform("com.example:allowlist-bom:1.0.0"))

    // Then just name the starter — no version needed
    implementation("com.example:allowlist-spring-boot-starter-boot3")
}
```

### Gradle CI matrix override

```kotlin
// Override Spring Boot version at test time via project property
val springBootVersion = project.findProperty("springBootVersion") as String? ?: "3.0.0"

dependencyManagement {
    imports {
        mavenBom("org.springframework.boot:spring-boot-dependencies:$springBootVersion")
    }
}
```

```bash
# Run tests against a specific Boot version
./gradlew test -PspringBootVersion=3.4.1
```

---

## Section 7: Consumer Usage Examples

### Minimal setup — service owns its own SecurityFilterChain

`build.gradle.kts`:
```kotlin
dependencies {
    implementation(platform("com.example:allowlist-bom:1.0.0"))
    implementation("com.example:allowlist-spring-boot-starter-boot3")
}
```

`application.yml`:
```yaml
allowlist:
  lists:
    finance-admins:
      - alice
      - bob.smith
```

Controller:
```java
@RestController
public class ReportController {

    @GetMapping("/reports/finance")
    @AllowList("finance-admins")
    public List<Report> getFinanceReports() {
        return reportService.getAll();
    }
}
```

### With library-managed JWT configuration

`application.yml`:
```yaml
allowlist:
  jwt:
    auto-configure: true
  lists:
    finance-admins:
      - alice

spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: https://auth.example.com
```

No `SecurityFilterChain` bean needed in the service.

### With Spring Cloud Config refresh

No code changes. When `spring-cloud-context` is on the classpath, the `AllowListRegistry` bean is automatically `@RefreshScope`. Calling `/actuator/refresh` (or a Spring Cloud Bus refresh event) re-binds `AllowListProperties` and recreates the registry with the new list values.

---

## Section 8: Issues and Known Trade-offs

### 1. Spring Security 7 API breakage risk

`AuthorizationManagerBeforeMethodInterceptor` and `AuthorizationManager<MethodInvocation>` are the stable Security 6 API surface. If Security 7 changes the method security contract, the Boot 4 starter isolates the fix. The `allowlist-spring-security` module can be forked into a `boot4` variant if required. Core is unaffected regardless.

**Action:** Monitor Spring Security 7 milestones. No action needed until Boot 4 GA.

### 2. `@RefreshScope` and CGLIB proxy interactions

`@RefreshScope` wraps the `AllowListRegistry` in a CGLIB scoped proxy. Double-proxying (e.g. from `@Transactional`) can cause unexpected behaviour. The `@ConditionalOnMissingBean` guard lets services override with their own strategy if this becomes a problem.

### 3. `SecurityFilterChain` ordering conflicts

`allowlist.jwt.auto-configure=true` registers a `SecurityFilterChain`. It is `@ConditionalOnMissingBean(SecurityFilterChain.class)` — only activates if the service has none. Do not combine `auto-configure=true` with a custom `SecurityFilterChain`.

### 4. Missing list name — misconfiguration vs typo

`@AllowList("finace-admins")` (typo) would throw `AllowListNotFoundException` at runtime on first request without the startup validator. The `AllowListStartupValidator` (registered by the starter) scans all beans at startup and fails fast if any referenced list name is not present in the registry.

### 5. Case sensitivity of subject matching

JWT `sub` values are case-sensitive by spec. YAML config values are whatever is typed. `Alice` ≠ `alice`. List values must exactly match the JWT `sub` claim. A `WARN` log is emitted on denial including the list name (but not the subject value — PII concern). A `allowlist.case-sensitive: false` option is noted for future consideration but not implemented.

### 6. Large allow-lists and memory

`MapAllowListRegistry` holds all lists in-memory. `HashSet.contains()` is O(1). Not a concern at current scale. The `AllowListRegistry` interface is the upgrade path to a database-backed implementation — no consumer code changes when swapped.

### 7. Thread safety on refresh

`@RefreshScope` proxies handle in-flight request safety: requests in-flight complete against the old instance, new requests get the new instance. This is standard Spring Cloud Config behaviour. No library-specific action needed.

### 8. `anyOf` / `allOf` multi-list annotation (future work)

Current: `@AllowList("name")` — single named list.

Recommended future shape:
```java
@AllowList(anyOf = {"finance-admins", "super-admins"}, allOf = {"active-users"})
```

The `AllowListAuthorizationManager` already receives the full `MethodInvocation` and `AllowListRegistry`. The logic change is localised there. Core and config modules are unaffected. The current `value()` element should be deprecated (not removed) when this is introduced.

### 9. Audit logging

Spring Security's `AuthorizationEventPublisher` automatically fires `AuthorizationDeniedEvent` and `AuthorizationGrantedEvent` when an `AuthorizationManager` returns a decision. Services can listen to these standard events for audit logging with no changes to this library. Document this in the consumer guide.

---

## Appendix A: Module directory layout (suggested)

```
allowlist/
├── allowlist-bom/
│   └── pom.xml
├── allowlist-core/
│   └── src/main/java/com/example/allowlist/core/
│       ├── AllowList.java
│       ├── AllowListRegistry.java
│       ├── MapAllowListRegistry.java
│       └── SubjectExtractor.java
├── allowlist-spring-security/
│   └── src/main/java/com/example/allowlist/spring/security/
│       ├── AllowListAuthorizationManager.java
│       ├── AllowListMethodSecurityConfiguration.java
│       └── AllowListNotFoundException.java
├── allowlist-spring-config/
│   └── src/main/java/com/example/allowlist/config/
│       ├── AllowListProperties.java
│       ├── AllowListRegistryFactory.java
│       ├── AllowListSpringConfigConfiguration.java
│       └── AllowListStartupValidator.java
├── allowlist-spring-boot-starter-boot3/
│   └── src/main/
│       ├── java/com/example/allowlist/boot3/
│       │   └── AllowListBoot3AutoConfiguration.java
│       └── resources/META-INF/spring/
│           └── org.springframework.boot.autoconfigure.AutoConfiguration.imports
├── allowlist-spring-boot-starter-boot4/
│   └── src/main/
│       ├── java/com/example/allowlist/boot4/
│       │   └── AllowListBoot4AutoConfiguration.java
│       └── resources/META-INF/spring/
│           └── org.springframework.boot.autoconfigure.AutoConfiguration.imports
└── pom.xml  (allowlist-parent)
```
