# AllowList Security Library Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-module Gradle library that enforces JWT subject-based allow-list access control on Spring controller methods via `@AllowList("list-name")`, targeting Spring Boot 3.x and 4.x.

**Architecture:** Six modules built in dependency order — pure Java core → Spring Security adapter → Spring Boot config binding → Boot 3 + Boot 4 starters + BOM. All Spring dependencies declared `compileOnly` so the library ships no Spring JARs. The consuming service's Boot BOM manages Spring versions at runtime.

**Tech Stack:** Java 17, Gradle 8 (Kotlin DSL), Spring Security 6 (`AuthorizationManager`), Spring Boot autoconfiguration (`@AutoConfiguration`, `AutoConfiguration.imports`), JUnit 5, Mockito 5, Spring Boot Test (`ApplicationContextRunner`)

**Spec:** `D:/tmp/claude/docs/superpowers/specs/2026-03-15-allowlist-library-design.md`

**Project root:** Create as a new standalone directory: `D:/tmp/allowlist/`

---

## Chunk 1: Gradle Project Scaffolding

### Task 1: Create root Gradle files

**Files:**
- Create: `D:/tmp/allowlist/gradle.properties`
- Create: `D:/tmp/allowlist/settings.gradle.kts`
- Create: `D:/tmp/allowlist/build.gradle.kts`
- Create: `D:/tmp/allowlist/gradle/libs.versions.toml`

- [ ] **Step 1: Create the project root directory and bootstrap the Gradle wrapper**

```bash
mkdir -p D:/tmp/allowlist
cd D:/tmp/allowlist
git init
# Bootstrap the wrapper so all subsequent steps use ./gradlew (not the system gradle).
# Requires gradle 8.x on PATH for this one-time bootstrap only.
gradle wrapper --gradle-version 8.11.1
```

- [ ] **Step 2: Create `gradle.properties`**

```properties
# gradle.properties
group=com.example
version=1.0.0-SNAPSHOT

# Compile against minimum supported versions — CI overrides these per matrix job
springBootVersion=3.0.0
springCloudVersion=2022.0.0

# Gradle performance
org.gradle.jvmargs=-Xmx2g -XX:+HeapDumpOnOutOfMemoryError
org.gradle.parallel=true
org.gradle.caching=true
```

- [ ] **Step 3: Create `settings.gradle.kts`**

```kotlin
// settings.gradle.kts
rootProject.name = "allowlist"

include(
    "allowlist-bom",
    "allowlist-core",
    "allowlist-spring-security",
    "allowlist-spring-config",
    "allowlist-spring-boot-starter-boot3",
    "allowlist-spring-boot-starter-boot4"
)
```

- [ ] **Step 4: Create `gradle/libs.versions.toml`**

```toml
# gradle/libs.versions.toml
[versions]
slf4j = "2.0.9"

[libraries]
# Spring deps — NO version here; version controlled by Spring Boot BOM platform import
spring-security-core         = { module = "org.springframework.security:spring-security-core" }
spring-security-config       = { module = "org.springframework.security:spring-security-config" }
spring-security-test         = { module = "org.springframework.security:spring-security-test" }
spring-boot-autoconfigure    = { module = "org.springframework.boot:spring-boot-autoconfigure" }
spring-boot-starter          = { module = "org.springframework.boot:spring-boot-starter" }
spring-boot-starter-test     = { module = "org.springframework.boot:spring-boot-starter-test" }
spring-boot-starter-security = { module = "org.springframework.boot:spring-boot-starter-security" }
spring-boot-starter-oauth2   = { module = "org.springframework.boot:spring-boot-starter-oauth2-resource-server" }
spring-cloud-context         = { module = "org.springframework.cloud:spring-cloud-context" }

# Non-Spring — version pinned here, not via BOM
slf4j-api = { module = "org.slf4j:slf4j-api", version.ref = "slf4j" }
```

- [ ] **Step 5: Create root `build.gradle.kts`**

```kotlin
// build.gradle.kts (root)
plugins {
    `java-library` apply false
    `java-platform` apply false
    `maven-publish` apply false
}

val springBootVersion: String by project
val springCloudVersion: String by project

allprojects {
    group = "com.example"
    repositories { mavenCentral() }
}

subprojects {
    if (name == "allowlist-bom") return@subprojects

    apply(plugin = "java-library")
    apply(plugin = "maven-publish")

    java {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        withSourcesJar()
        withJavadocJar()
    }

    // Gradle-native BOM import — no io.spring.dependency-management plugin needed.
    // Use platform() not enforcedPlatform() so consumers can override versions.
    dependencies {
        implementation(platform("org.springframework.boot:spring-boot-dependencies:$springBootVersion"))
        implementation(platform("org.springframework.cloud:spring-cloud-dependencies:$springCloudVersion"))
    }

    tasks.withType<Test> { useJUnitPlatform() }

    publishing {
        publications {
            create<MavenPublication>("maven") { from(components["java"]) }
        }
        repositories {
            maven {
                name = "internal"
                url = uri(
                    if (version.toString().endsWith("SNAPSHOT"))
                        "https://nexus.example.com/repository/snapshots"
                    else
                        "https://nexus.example.com/repository/releases"
                )
                credentials {
                    username = System.getenv("NEXUS_USER")
                    password = System.getenv("NEXUS_PASSWORD")
                }
            }
        }
    }
}
```

- [ ] **Step 6: Commit root scaffolding (including wrapper)**

```bash
git add gradle.properties settings.gradle.kts build.gradle.kts gradle/libs.versions.toml \
        gradlew gradlew.bat gradle/wrapper/
git commit -m "chore: add root Gradle project scaffolding and wrapper"
```

---

### Task 2: Create module directories and build files

**Files:**
- Create: `allowlist-bom/build.gradle.kts`
- Create: `allowlist-core/build.gradle.kts`
- Create: `allowlist-spring-security/build.gradle.kts`
- Create: `allowlist-spring-config/build.gradle.kts`
- Create: `allowlist-spring-boot-starter-boot3/build.gradle.kts`
- Create: `allowlist-spring-boot-starter-boot4/build.gradle.kts`

- [ ] **Step 1: Create all module source directories**

```bash
for module in allowlist-bom allowlist-core allowlist-spring-security allowlist-spring-config allowlist-spring-boot-starter-boot3 allowlist-spring-boot-starter-boot4; do
    mkdir -p $module/src/main/java
    mkdir -p $module/src/test/java
done

# Resources for starters (AutoConfiguration.imports)
mkdir -p allowlist-spring-boot-starter-boot3/src/main/resources/META-INF/spring
mkdir -p allowlist-spring-boot-starter-boot4/src/main/resources/META-INF/spring
```

- [ ] **Step 2: Create `allowlist-bom/build.gradle.kts`**

```kotlin
// allowlist-bom/build.gradle.kts
plugins {
    `java-platform`
    `maven-publish`
}

javaPlatform { allowDependencies() }

dependencies {
    constraints {
        api(project(":allowlist-core"))
        api(project(":allowlist-spring-security"))
        api(project(":allowlist-spring-config"))
        api(project(":allowlist-spring-boot-starter-boot3"))
        api(project(":allowlist-spring-boot-starter-boot4"))
    }
}

publishing {
    publications {
        create<MavenPublication>("allowlistBom") {
            from(components["javaPlatform"])
            artifactId = "allowlist-bom"
        }
    }
}
```

- [ ] **Step 3: Create `allowlist-core/build.gradle.kts`**

```kotlin
// allowlist-core/build.gradle.kts
plugins { `java-library` }

dependencies {
    testImplementation("org.junit.jupiter:junit-jupiter")
    testImplementation("org.assertj:assertj-core")
}
```

- [ ] **Step 4: Create `allowlist-spring-security/build.gradle.kts`**

```kotlin
// allowlist-spring-security/build.gradle.kts
plugins { `java-library` }

dependencies {
    api(project(":allowlist-core"))
    api(libs.slf4j.api)

    compileOnly(libs.spring.security.core)
    compileOnly(libs.spring.security.config)

    // compileOnly is available at test compile time, but NOT test runtime — add runtime deps
    testImplementation(libs.spring.boot.starter.test)
    testImplementation(libs.spring.boot.starter.security)
    testImplementation("org.mockito:mockito-core")
}
```

- [ ] **Step 5: Create `allowlist-spring-config/build.gradle.kts`**

```kotlin
// allowlist-spring-config/build.gradle.kts
plugins { `java-library` }

dependencies {
    // api not compileOnly — AllowListSpringConfigConfiguration @Imports spring-security classes
    api(project(":allowlist-spring-security"))

    compileOnly(libs.spring.boot.autoconfigure)
    compileOnly(libs.spring.boot.starter)
    compileOnly(libs.spring.cloud.context)   // optional — @RefreshScope variant

    testImplementation(libs.spring.boot.starter.test)
    testImplementation(libs.spring.boot.starter.security)
    testImplementation(libs.spring.boot.starter.oauth2)
}
```

- [ ] **Step 6: Create `allowlist-spring-boot-starter-boot3/build.gradle.kts`**

```kotlin
// allowlist-spring-boot-starter-boot3/build.gradle.kts
plugins { `java-library` }

dependencies {
    api(project(":allowlist-spring-config"))

    compileOnly(libs.spring.boot.autoconfigure)
    compileOnly(libs.spring.boot.starter)
    compileOnly(libs.spring.boot.starter.security)
    compileOnly(libs.spring.boot.starter.oauth2)

    testImplementation(libs.spring.boot.starter.test)
    testImplementation(libs.spring.security.test)
    testImplementation(libs.spring.boot.starter.oauth2)
}
```

- [ ] **Step 7: Create `allowlist-spring-boot-starter-boot4/build.gradle.kts`** (identical to boot3 initially)

```kotlin
// allowlist-spring-boot-starter-boot4/build.gradle.kts
plugins { `java-library` }

dependencies {
    api(project(":allowlist-spring-config"))

    compileOnly(libs.spring.boot.autoconfigure)
    compileOnly(libs.spring.boot.starter)
    compileOnly(libs.spring.boot.starter.security)
    compileOnly(libs.spring.boot.starter.oauth2)

    testImplementation(libs.spring.boot.starter.test)
    testImplementation(libs.spring.security.test)
    testImplementation(libs.spring.boot.starter.oauth2)
}
```

- [ ] **Step 8: Verify the build compiles with no sources yet**

```bash
./gradlew build
```

Expected: `BUILD SUCCESSFUL` (no sources yet, all modules compile empty)

- [ ] **Step 9: Commit module build files**

```bash
git add allowlist-*/build.gradle.kts
git commit -m "chore: add module build files for all six allowlist modules"
```

---

## Chunk 2: `allowlist-core` — Pure Java API

### Task 3: `@AllowList` annotation and `AllowListRegistry` interface

**Files:**
- Create: `allowlist-core/src/main/java/com/example/allowlist/core/AllowList.java`
- Create: `allowlist-core/src/main/java/com/example/allowlist/core/AllowListRegistry.java`
- Create: `allowlist-core/src/main/java/com/example/allowlist/core/SubjectExtractor.java`
- Create: `allowlist-core/src/test/java/com/example/allowlist/core/AllowListAnnotationTest.java`

- [ ] **Step 1: Write the failing annotation test**

```java
// allowlist-core/src/test/java/com/example/allowlist/core/AllowListAnnotationTest.java
package com.example.allowlist.core;

import org.junit.jupiter.api.Test;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.reflect.Method;
import static org.assertj.core.api.Assertions.assertThat;

class AllowListAnnotationTest {

    @AllowList("finance-admins")
    void annotatedMethod() {}

    @Test
    void annotationIsRetainedAtRuntime() throws NoSuchMethodException {
        Method method = AllowListAnnotationTest.class.getDeclaredMethod("annotatedMethod");
        AllowList annotation = method.getAnnotation(AllowList.class);

        assertThat(annotation).isNotNull();
        assertThat(annotation.value()).isEqualTo("finance-admins");
    }

    @AllowList("team-leads")
    static class AnnotatedClass {
        void someMethod() {}
    }

    @Test
    void annotationCanBePlacedOnClass() {
        AllowList annotation = AnnotatedClass.class.getAnnotation(AllowList.class);

        assertThat(annotation).isNotNull();
        assertThat(annotation.value()).isEqualTo("team-leads");
    }
}
```

- [ ] **Step 2: Run the test to confirm it fails**

```bash
./gradlew :allowlist-core:test --tests "com.example.allowlist.core.AllowListAnnotationTest"
```

Expected: FAIL — `AllowList` class not found

- [ ] **Step 3: Create `AllowList.java`**

```java
// allowlist-core/src/main/java/com/example/allowlist/core/AllowList.java
package com.example.allowlist.core;

import java.lang.annotation.*;

@Target({ElementType.METHOD, ElementType.TYPE})
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface AllowList {
    /**
     * The name of the allow-list to check against.
     * Must match a key under allowlist.lists in configuration.
     * When placed on a class, applies to all public methods of that class.
     */
    String value();
}
```

- [ ] **Step 4: Create `AllowListRegistry.java`**

```java
// allowlist-core/src/main/java/com/example/allowlist/core/AllowListRegistry.java
package com.example.allowlist.core;

public interface AllowListRegistry {
    /** Returns true if subject appears in the named list. */
    boolean isAllowed(String listName, String subject);

    /** Returns true if the named list is registered (even if empty). */
    boolean listExists(String listName);
}
```

- [ ] **Step 5: Create `SubjectExtractor.java`**

```java
// allowlist-core/src/main/java/com/example/allowlist/core/SubjectExtractor.java
package com.example.allowlist.core;

/**
 * Reserved for future use. Not wired in the default flow.
 * The subject is currently read from Authentication.getName() by Spring Security.
 * When implemented, the starter will detect a SubjectExtractor bean via
 * @ConditionalOnBean and pass it to AllowListAuthorizationManager.
 */
public interface SubjectExtractor<T> {
    String extract(T source);
}
```

- [ ] **Step 6: Run the annotation test to confirm it passes**

```bash
./gradlew :allowlist-core:test --tests "com.example.allowlist.core.AllowListAnnotationTest"
```

Expected: `BUILD SUCCESSFUL`, both tests PASS

- [ ] **Step 7: Commit**

```bash
git add allowlist-core/src/
git commit -m "feat(core): add @AllowList annotation, AllowListRegistry interface, SubjectExtractor"
```

---

### Task 4: `MapAllowListRegistry` implementation

**Files:**
- Create: `allowlist-core/src/main/java/com/example/allowlist/core/MapAllowListRegistry.java`
- Create: `allowlist-core/src/test/java/com/example/allowlist/core/MapAllowListRegistryTest.java`

- [ ] **Step 1: Write failing tests**

```java
// allowlist-core/src/test/java/com/example/allowlist/core/MapAllowListRegistryTest.java
package com.example.allowlist.core;

import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.assertThat;

class MapAllowListRegistryTest {

    @Test
    void allowsSubjectPresentInList() {
        AllowListRegistry registry = new MapAllowListRegistry(
            Map.of("admins", List.of("alice", "bob")));

        assertThat(registry.isAllowed("admins", "alice")).isTrue();
        assertThat(registry.isAllowed("admins", "bob")).isTrue();
    }

    @Test
    void deniesSubjectAbsentFromList() {
        AllowListRegistry registry = new MapAllowListRegistry(
            Map.of("admins", List.of("alice")));

        assertThat(registry.isAllowed("admins", "mallory")).isFalse();
    }

    @Test
    void deniesWhenListDoesNotExist() {
        AllowListRegistry registry = new MapAllowListRegistry(Map.of());

        assertThat(registry.isAllowed("nonexistent", "alice")).isFalse();
    }

    @Test
    void listExistsReturnsTrueForConfiguredList() {
        AllowListRegistry registry = new MapAllowListRegistry(
            Map.of("admins", List.of("alice")));

        assertThat(registry.listExists("admins")).isTrue();
    }

    @Test
    void listExistsReturnsFalseForUnknownList() {
        AllowListRegistry registry = new MapAllowListRegistry(Map.of());

        assertThat(registry.listExists("nonexistent")).isFalse();
    }

    @Test
    void listExistsReturnsTrueForEmptyList() {
        AllowListRegistry registry = new MapAllowListRegistry(
            Map.of("empty-list", List.of()));

        assertThat(registry.listExists("empty-list")).isTrue();
    }

    @Test
    void subjectMatchingIsCaseSensitive() {
        AllowListRegistry registry = new MapAllowListRegistry(
            Map.of("admins", List.of("alice")));

        assertThat(registry.isAllowed("admins", "Alice")).isFalse();
        assertThat(registry.isAllowed("admins", "ALICE")).isFalse();
    }

    @Test
    void constructorMakesDefensiveCopy() {
        java.util.List<String> mutableList = new java.util.ArrayList<>(List.of("alice"));
        java.util.Map<String, java.util.List<String>> mutableMap = new java.util.HashMap<>();
        mutableMap.put("admins", mutableList);

        AllowListRegistry registry = new MapAllowListRegistry(mutableMap);

        // Mutate source after construction — registry should be unaffected
        mutableList.add("mallory");
        mutableMap.put("new-list", List.of("eve"));

        assertThat(registry.isAllowed("admins", "mallory")).isFalse();
        assertThat(registry.listExists("new-list")).isFalse();
    }
}
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
./gradlew :allowlist-core:test --tests "com.example.allowlist.core.MapAllowListRegistryTest"
```

Expected: FAIL — `MapAllowListRegistry` class not found

- [ ] **Step 3: Create `MapAllowListRegistry.java`**

```java
// allowlist-core/src/main/java/com/example/allowlist/core/MapAllowListRegistry.java
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

- [ ] **Step 4: Run all tests in the module to confirm they pass**

```bash
./gradlew :allowlist-core:test
```

Expected: `BUILD SUCCESSFUL`, all 10 tests PASS (2 from AllowListAnnotationTest + 8 from MapAllowListRegistryTest)

- [ ] **Step 5: Commit**

```bash
git add allowlist-core/src/main/java/com/example/allowlist/core/MapAllowListRegistry.java \
        allowlist-core/src/test/java/com/example/allowlist/core/MapAllowListRegistryTest.java
git commit -m "feat(core): implement MapAllowListRegistry with immutable snapshot and O(1) lookup"
```

---

## Chunk 3: `allowlist-spring-security` — Spring Security Integration

### Task 5: Exception types

**Files:**
- Create: `allowlist-spring-security/src/main/java/com/example/allowlist/spring/security/AllowListNotFoundException.java`
- Create: `allowlist-spring-security/src/main/java/com/example/allowlist/spring/security/AllowListMisconfigurationException.java`
- Create: `allowlist-spring-security/src/test/java/com/example/allowlist/spring/security/ExceptionTypesTest.java`

- [ ] **Step 1: Write the failing test**

```java
// allowlist-spring-security/src/test/java/com/example/allowlist/spring/security/ExceptionTypesTest.java
package com.example.allowlist.spring.security;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class ExceptionTypesTest {

    @Test
    void allowListNotFoundExceptionIsRuntimeException() {
        AllowListNotFoundException ex = new AllowListNotFoundException("test message");
        assertThat(ex).isInstanceOf(RuntimeException.class);
        assertThat(ex.getMessage()).isEqualTo("test message");
    }

    @Test
    void allowListMisconfigurationExceptionIsRuntimeException() {
        AllowListMisconfigurationException ex =
            new AllowListMisconfigurationException("startup error");
        assertThat(ex).isInstanceOf(RuntimeException.class);
        assertThat(ex.getMessage()).isEqualTo("startup error");
    }

    @Test
    void exceptionTypesAreDistinct() {
        assertThat(AllowListNotFoundException.class)
            .isNotEqualTo(AllowListMisconfigurationException.class);
    }
}
```

- [ ] **Step 2: Run to confirm failure**

```bash
./gradlew :allowlist-spring-security:test --tests "com.example.allowlist.spring.security.ExceptionTypesTest"
```

Expected: FAIL — classes not found

- [ ] **Step 3: Create both exception classes**

```java
// allowlist-spring-security/src/main/java/com/example/allowlist/spring/security/AllowListNotFoundException.java
package com.example.allowlist.spring.security;

/**
 * Thrown at RUNTIME when a named list cannot be found during an access check.
 * Maps to HTTP 500 by default; services may remap to 403 via @ExceptionHandler.
 */
public class AllowListNotFoundException extends RuntimeException {
    public AllowListNotFoundException(String message) {
        super(message);
    }
}
```

```java
// allowlist-spring-security/src/main/java/com/example/allowlist/spring/security/AllowListMisconfigurationException.java
package com.example.allowlist.spring.security;

/**
 * Thrown at STARTUP by AllowListStartupValidator when a list name referenced
 * by @AllowList has no corresponding entry in configuration.
 * This is a fatal startup failure, not a per-request condition.
 */
public class AllowListMisconfigurationException extends RuntimeException {
    public AllowListMisconfigurationException(String message) {
        super(message);
    }
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
./gradlew :allowlist-spring-security:test --tests "com.example.allowlist.spring.security.ExceptionTypesTest"
```

Expected: `BUILD SUCCESSFUL`, all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add allowlist-spring-security/src/
git commit -m "feat(spring-security): add AllowListNotFoundException and AllowListMisconfigurationException"
```

---

### Task 6: `AllowListAuthorizationManager`

**Files:**
- Create: `allowlist-spring-security/src/main/java/com/example/allowlist/spring/security/AllowListAuthorizationManager.java`
- Create: `allowlist-spring-security/src/test/java/com/example/allowlist/spring/security/AllowListAuthorizationManagerTest.java`

- [ ] **Step 1: Write failing tests**

```java
// allowlist-spring-security/src/test/java/com/example/allowlist/spring/security/AllowListAuthorizationManagerTest.java
package com.example.allowlist.spring.security;

import com.example.allowlist.core.AllowList;
import com.example.allowlist.core.AllowListRegistry;
import com.example.allowlist.core.MapAllowListRegistry;
import org.aopalliance.intercept.MethodInvocation;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.authorization.AuthorizationDecision;
import org.springframework.security.core.Authentication;

import java.lang.reflect.Method;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.*;

class AllowListAuthorizationManagerTest {

    // Test controller with method-level annotation
    static class MethodAnnotatedController {
        @AllowList("admins")
        public void adminEndpoint() {}

        public void openEndpoint() {}
    }

    // Test controller with class-level annotation
    @AllowList("team-leads")
    static class ClassAnnotatedController {
        public void anyEndpoint() {}
    }

    // Test controller with both — method takes precedence
    @AllowList("class-list")
    static class BothAnnotationsController {
        @AllowList("method-list")
        public void methodAnnotatedEndpoint() {}

        public void classAnnotatedEndpoint() {}
    }

    private MethodInvocation invocationFor(Class<?> controllerClass, String methodName)
            throws NoSuchMethodException {
        MethodInvocation inv = mock(MethodInvocation.class);
        Method method = controllerClass.getMethod(methodName);
        when(inv.getMethod()).thenReturn(method);
        return inv;
    }

    private Authentication authFor(String subject) {
        return new UsernamePasswordAuthenticationToken(subject, null, List.of());
    }

    @Test
    void allowsAccessWhenSubjectIsInList() throws NoSuchMethodException {
        AllowListRegistry registry = new MapAllowListRegistry(
            Map.of("admins", List.of("alice", "bob")));
        AllowListAuthorizationManager manager = new AllowListAuthorizationManager(registry);

        AuthorizationDecision decision = manager.check(
            () -> authFor("alice"),
            invocationFor(MethodAnnotatedController.class, "adminEndpoint"));

        assertThat(decision.isGranted()).isTrue();
    }

    @Test
    void deniesAccessWhenSubjectNotInList() throws NoSuchMethodException {
        AllowListRegistry registry = new MapAllowListRegistry(
            Map.of("admins", List.of("alice")));
        AllowListAuthorizationManager manager = new AllowListAuthorizationManager(registry);

        AuthorizationDecision decision = manager.check(
            () -> authFor("mallory"),
            invocationFor(MethodAnnotatedController.class, "adminEndpoint"));

        assertThat(decision.isGranted()).isFalse();
    }

    @Test
    void throwsAllowListNotFoundExceptionWhenListNotConfigured() throws NoSuchMethodException {
        AllowListRegistry registry = new MapAllowListRegistry(Map.of()); // no lists configured
        AllowListAuthorizationManager manager = new AllowListAuthorizationManager(registry);

        assertThatThrownBy(() -> manager.check(
                () -> authFor("alice"),
                invocationFor(MethodAnnotatedController.class, "adminEndpoint")))
            .isInstanceOf(AllowListNotFoundException.class)
            .hasMessageContaining("admins");
    }

    @Test
    void allowsAccessWhenMethodHasNoAnnotation() throws NoSuchMethodException {
        AllowListRegistry registry = new MapAllowListRegistry(Map.of());
        AllowListAuthorizationManager manager = new AllowListAuthorizationManager(registry);

        AuthorizationDecision decision = manager.check(
            () -> authFor("anyone"),
            invocationFor(MethodAnnotatedController.class, "openEndpoint"));

        assertThat(decision.isGranted()).isTrue();
    }

    @Test
    void usesClassLevelAnnotationWhenMethodHasNone() throws NoSuchMethodException {
        AllowListRegistry registry = new MapAllowListRegistry(
            Map.of("team-leads", List.of("charlie")));
        AllowListAuthorizationManager manager = new AllowListAuthorizationManager(registry);

        AuthorizationDecision decision = manager.check(
            () -> authFor("charlie"),
            invocationFor(ClassAnnotatedController.class, "anyEndpoint"));

        assertThat(decision.isGranted()).isTrue();
    }

    @Test
    void methodAnnotationTakesPrecedenceOverClassAnnotation() throws NoSuchMethodException {
        AllowListRegistry registry = new MapAllowListRegistry(
            Map.of("method-list", List.of("alice"), "class-list", List.of("bob")));
        AllowListAuthorizationManager manager = new AllowListAuthorizationManager(registry);

        // "alice" is in method-list — should be allowed
        assertThat(manager.check(
            () -> authFor("alice"),
            invocationFor(BothAnnotationsController.class, "methodAnnotatedEndpoint"))
            .isGranted()).isTrue();

        // "bob" is in class-list only, not method-list — should be denied
        assertThat(manager.check(
            () -> authFor("bob"),
            invocationFor(BothAnnotationsController.class, "methodAnnotatedEndpoint"))
            .isGranted()).isFalse();
    }
}
```

- [ ] **Step 2: Run to confirm failure**

```bash
./gradlew :allowlist-spring-security:test --tests "com.example.allowlist.spring.security.AllowListAuthorizationManagerTest"
```

Expected: FAIL — `AllowListAuthorizationManager` not found

- [ ] **Step 3: Create `AllowListAuthorizationManager.java`**

```java
// allowlist-spring-security/src/main/java/com/example/allowlist/spring/security/AllowListAuthorizationManager.java
package com.example.allowlist.spring.security;

import com.example.allowlist.core.AllowList;
import com.example.allowlist.core.AllowListRegistry;
import org.aopalliance.intercept.MethodInvocation;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.authorization.AuthorizationDecision;
import org.springframework.security.authorization.AuthorizationManager;
import org.springframework.security.core.Authentication;

import java.util.function.Supplier;

public class AllowListAuthorizationManager
        implements AuthorizationManager<MethodInvocation> {

    private static final Logger log =
        LoggerFactory.getLogger(AllowListAuthorizationManager.class);

    // NOTE: When @RefreshScope is active, Spring injects the CGLIB scoped proxy
    // for AllowListRegistry — not the raw target. All calls through this field
    // are delegated to the current target by the proxy after a refresh.
    // NEVER call AopUtils.getTargetObject(registry) — it bypasses the proxy
    // and captures a stale instance.
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
            throw new AllowListNotFoundException(
                "No allow-list configured with name: '" + listName + "'");
        }

        boolean allowed = registry.isAllowed(listName, subject);
        if (!allowed) {
            // Log list name only — subject value is PII and must not appear in logs
            log.warn("AllowList denial: list='{}' method='{}'",
                listName,
                invocation.getMethod().getDeclaringClass().getSimpleName()
                    + "#" + invocation.getMethod().getName());
        }
        return new AuthorizationDecision(allowed);
    }

    // @AllowList is @Target({METHOD, TYPE}).
    // Method-level annotation takes precedence over class-level.
    private AllowList findAnnotation(MethodInvocation invocation) {
        AllowList ann = invocation.getMethod().getAnnotation(AllowList.class);
        if (ann != null) return ann;
        return invocation.getMethod().getDeclaringClass().getAnnotation(AllowList.class);
    }
}
```

- [ ] **Step 4: Run all tests in the module to confirm they pass**

```bash
./gradlew :allowlist-spring-security:test
```

Expected: `BUILD SUCCESSFUL`, all tests PASS

- [ ] **Step 5: Commit**

```bash
git add allowlist-spring-security/src/
git commit -m "feat(spring-security): implement AllowListAuthorizationManager with deny logging and class-level annotation support"
```

---

### Task 7: `AllowListMethodSecurityConfiguration`

**Files:**
- Create: `allowlist-spring-security/src/main/java/com/example/allowlist/spring/security/AllowListMethodSecurityConfiguration.java`
- Create: `allowlist-spring-security/src/test/java/com/example/allowlist/spring/security/AllowListMethodSecurityConfigurationTest.java`

- [ ] **Step 1: Write the failing test**

```java
// allowlist-spring-security/src/test/java/com/example/allowlist/spring/security/AllowListMethodSecurityConfigurationTest.java
package com.example.allowlist.spring.security;

import com.example.allowlist.core.MapAllowListRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.security.authorization.method.AuthorizationManagerBeforeMethodInterceptor;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class AllowListMethodSecurityConfigurationTest {

    @Test
    void createsInterceptorBean() {
        AllowListMethodSecurityConfiguration config =
            new AllowListMethodSecurityConfiguration();
        AllowListAuthorizationManager manager =
            new AllowListAuthorizationManager(new MapAllowListRegistry(Map.of()));

        AuthorizationManagerBeforeMethodInterceptor interceptor =
            config.allowListMethodInterceptor(manager);

        assertThat(interceptor).isNotNull();
        assertThat(interceptor.getOrder()).isLessThan(Integer.MAX_VALUE);
    }
}
```

- [ ] **Step 2: Run to confirm failure**

```bash
./gradlew :allowlist-spring-security:test --tests "com.example.allowlist.spring.security.AllowListMethodSecurityConfigurationTest"
```

Expected: FAIL — `AllowListMethodSecurityConfiguration` not found

- [ ] **Step 3: Create `AllowListMethodSecurityConfiguration.java`**

```java
// allowlist-spring-security/src/main/java/com/example/allowlist/spring/security/AllowListMethodSecurityConfiguration.java
package com.example.allowlist.spring.security;

import com.example.allowlist.core.AllowList;
import org.springframework.aop.Pointcut;
import org.springframework.aop.support.ComposablePointcut;
import org.springframework.aop.support.annotation.AnnotationMatchingPointcut;
import org.springframework.context.annotation.Bean;
import org.springframework.security.authorization.method.AuthorizationManagerBeforeMethodInterceptor;

public class AllowListMethodSecurityConfiguration {

    @Bean
    public AuthorizationManagerBeforeMethodInterceptor allowListMethodInterceptor(
            AllowListAuthorizationManager authorizationManager) {

        // Match methods directly annotated with @AllowList
        Pointcut methodAnnotated = new AnnotationMatchingPointcut(null, AllowList.class);
        // Also match all methods on classes annotated with @AllowList (class-level default)
        Pointcut classAnnotated  = new AnnotationMatchingPointcut(AllowList.class, true);
        // Union: intercept if EITHER condition holds
        Pointcut combined = new ComposablePointcut(methodAnnotated).union(classAnnotated);

        return new AuthorizationManagerBeforeMethodInterceptor(combined, authorizationManager);
    }
}

// Note: not a @Configuration class — imported explicitly by the autoconfiguration.
// This prevents the module from self-activating on the classpath.
```

- [ ] **Step 4: Run all tests in the module**

```bash
./gradlew :allowlist-spring-security:test
```

Expected: `BUILD SUCCESSFUL`, all tests PASS

- [ ] **Step 5: Commit**

```bash
git add allowlist-spring-security/src/main/java/com/example/allowlist/spring/security/AllowListMethodSecurityConfiguration.java \
        allowlist-spring-security/src/test/java/com/example/allowlist/spring/security/AllowListMethodSecurityConfigurationTest.java
git commit -m "feat(spring-security): add AllowListMethodSecurityConfiguration with ComposablePointcut for method and class-level interception"
```

---

## Chunk 4: `allowlist-spring-config` — Configuration Binding

### Task 8: `AllowListProperties` and `AllowListRegistryFactory`

**Files:**
- Create: `allowlist-spring-config/src/main/java/com/example/allowlist/config/AllowListProperties.java`
- Create: `allowlist-spring-config/src/main/java/com/example/allowlist/config/AllowListRegistryFactory.java`
- Create: `allowlist-spring-config/src/test/java/com/example/allowlist/config/AllowListPropertiesTest.java`

- [ ] **Step 1: Write failing tests**

```java
// allowlist-spring-config/src/test/java/com/example/allowlist/config/AllowListPropertiesTest.java
package com.example.allowlist.config;

import com.example.allowlist.core.AllowListRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.TestPropertySource;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(classes = AllowListPropertiesTest.TestConfig.class)
@TestPropertySource(properties = {
    "allowlist.lists.admins=alice,bob",
    "allowlist.lists.readers=dave,eve",
    "allowlist.jwt.auto-configure=false"
})
class AllowListPropertiesTest {

    @EnableConfigurationProperties(AllowListProperties.class)
    static class TestConfig {}

    @Autowired
    AllowListProperties properties;

    @Test
    void bindsListsFromProperties() {
        assertThat(properties.getLists()).containsKey("admins");
        assertThat(properties.getLists().get("admins")).contains("alice", "bob");
        assertThat(properties.getLists()).containsKey("readers");
    }

    @Test
    void jwtAutoConfigureDefaultsToFalse() {
        assertThat(properties.getJwt().isAutoConfigure()).isFalse();
    }

    @Test
    void factoryCreatesRegistryFromProperties() {
        AllowListRegistry registry = AllowListRegistryFactory.create(properties);

        assertThat(registry.isAllowed("admins", "alice")).isTrue();
        assertThat(registry.isAllowed("admins", "mallory")).isFalse();
        assertThat(registry.listExists("readers")).isTrue();
    }
}
```

- [ ] **Step 2: Run to confirm failure**

```bash
./gradlew :allowlist-spring-config:test --tests "com.example.allowlist.config.AllowListPropertiesTest"
```

Expected: FAIL — classes not found

- [ ] **Step 3: Create `AllowListProperties.java`**

```java
// allowlist-spring-config/src/main/java/com/example/allowlist/config/AllowListProperties.java
package com.example.allowlist.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

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

- [ ] **Step 4: Create `AllowListRegistryFactory.java`**

```java
// allowlist-spring-config/src/main/java/com/example/allowlist/config/AllowListRegistryFactory.java
package com.example.allowlist.config;

import com.example.allowlist.core.AllowListRegistry;
import com.example.allowlist.core.MapAllowListRegistry;

public class AllowListRegistryFactory {

    public static AllowListRegistry create(AllowListProperties properties) {
        return new MapAllowListRegistry(properties.getLists());
    }

    private AllowListRegistryFactory() {}
}
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
./gradlew :allowlist-spring-config:test --tests "com.example.allowlist.config.AllowListPropertiesTest"
```

Expected: `BUILD SUCCESSFUL`, all 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add allowlist-spring-config/src/
git commit -m "feat(spring-config): add AllowListProperties @ConfigurationProperties binding and AllowListRegistryFactory"
```

---

### Task 9: `AllowListStartupValidator`

**Files:**
- Create: `allowlist-spring-config/src/main/java/com/example/allowlist/config/AllowListStartupValidator.java`
- Create: `allowlist-spring-config/src/test/java/com/example/allowlist/config/AllowListStartupValidatorTest.java`

- [ ] **Step 1: Write failing tests**

```java
// allowlist-spring-config/src/test/java/com/example/allowlist/config/AllowListStartupValidatorTest.java
package com.example.allowlist.config;

import com.example.allowlist.core.AllowList;
import com.example.allowlist.core.AllowListRegistry;
import com.example.allowlist.core.MapAllowListRegistry;
import com.example.allowlist.spring.security.AllowListMisconfigurationException;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class AllowListStartupValidatorTest {

    // A bean whose method references an existing list — should pass validation
    static class GoodController {
        @AllowList("admins")
        public void adminEndpoint() {}
    }

    // A bean whose method references a non-existent list — should fail validation
    static class BadController {
        @AllowList("nonexistent-list")
        public void someEndpoint() {}
    }

    // A bean with class-level annotation referencing a non-existent list
    @AllowList("also-nonexistent")
    static class BadClassAnnotatedController {
        public void anyEndpoint() {}
    }

    @Test
    void passesValidationWhenAllListsExist() {
        AllowListRegistry registry = new MapAllowListRegistry(
            Map.of("admins", java.util.List.of("alice")));
        AllowListStartupValidator validator = new AllowListStartupValidator(registry);

        // Should not throw
        new ApplicationContextRunner()
            .withBean(GoodController.class)
            .withBean("validator", AllowListStartupValidator.class,
                () -> validator)
            .run(context -> assertThat(context).hasNotFailed());
    }

    @Test
    void failsValidationWhenMethodAnnotationReferencesUnknownList() {
        AllowListRegistry registry = new MapAllowListRegistry(Map.of()); // no lists
        AllowListStartupValidator validator = new AllowListStartupValidator(registry);

        new ApplicationContextRunner()
            .withBean(BadController.class)
            .withBean("validator", AllowListStartupValidator.class,
                () -> validator)
            .run(context -> {
                assertThat(context).hasFailed();
                assertThat(context.getStartupFailure())
                    .rootCause()
                    .isInstanceOf(AllowListMisconfigurationException.class)
                    .hasMessageContaining("nonexistent-list");
            });
    }

    @Test
    void failsValidationWhenClassAnnotationReferencesUnknownList() {
        AllowListRegistry registry = new MapAllowListRegistry(Map.of());
        AllowListStartupValidator validator = new AllowListStartupValidator(registry);

        new ApplicationContextRunner()
            .withBean(BadClassAnnotatedController.class)
            .withBean("validator", AllowListStartupValidator.class,
                () -> validator)
            .run(context -> {
                assertThat(context).hasFailed();
                assertThat(context.getStartupFailure())
                    .rootCause()
                    .isInstanceOf(AllowListMisconfigurationException.class)
                    .hasMessageContaining("also-nonexistent");
            });
    }
}
```

- [ ] **Step 2: Run to confirm failure**

```bash
./gradlew :allowlist-spring-config:test --tests "com.example.allowlist.config.AllowListStartupValidatorTest"
```

Expected: FAIL — `AllowListStartupValidator` not found

- [ ] **Step 3: Create `AllowListStartupValidator.java`**

```java
// allowlist-spring-config/src/main/java/com/example/allowlist/config/AllowListStartupValidator.java
package com.example.allowlist.config;

import com.example.allowlist.core.AllowList;
import com.example.allowlist.core.AllowListRegistry;
import com.example.allowlist.spring.security.AllowListMisconfigurationException;
import org.springframework.aop.support.AopUtils;
import org.springframework.context.ApplicationListener;
import org.springframework.context.event.ContextRefreshedEvent;
import org.springframework.core.annotation.AnnotationUtils;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;

public class AllowListStartupValidator
        implements ApplicationListener<ContextRefreshedEvent> {

    private final AllowListRegistry registry;

    public AllowListStartupValidator(AllowListRegistry registry) {
        this.registry = registry;
    }

    @Override
    public void onApplicationEvent(ContextRefreshedEvent event) {
        String[] beanNames = event.getApplicationContext().getBeanDefinitionNames();
        List<String> errors = new ArrayList<>();

        for (String beanName : beanNames) {
            try {
                Object bean = event.getApplicationContext().getBean(beanName);
                // AopUtils.getTargetClass() unwraps CGLIB proxies (e.g. @Transactional
                // controllers) so we inspect annotations on the real class, not the proxy.
                Class<?> targetClass = AopUtils.getTargetClass(bean);

                for (Method method : targetClass.getMethods()) {
                    // AnnotationUtils.findAnnotation handles meta-annotations and
                    // annotation inheritance correctly across proxy boundaries.
                    AllowList ann = AnnotationUtils.findAnnotation(method, AllowList.class);
                    if (ann != null && !registry.listExists(ann.value())) {
                        errors.add(targetClass.getSimpleName() + "#" + method.getName()
                            + " references unknown list: '" + ann.value() + "'");
                    }
                }

                // Check class-level @AllowList
                AllowList classAnn = AnnotationUtils.findAnnotation(targetClass, AllowList.class);
                if (classAnn != null && !registry.listExists(classAnn.value())) {
                    errors.add(targetClass.getSimpleName()
                        + " (class-level) references unknown list: '" + classAnn.value() + "'");
                }
            } catch (Exception ignored) { /* skip uninstantiable beans */ }
        }

        if (!errors.isEmpty()) {
            throw new AllowListMisconfigurationException(
                "AllowList configuration errors detected at startup:\n"
                + String.join("\n", errors));
        }
    }
}
```

- [ ] **Step 4: Run all tests in the module**

```bash
./gradlew :allowlist-spring-config:test
```

Expected: `BUILD SUCCESSFUL`, all tests PASS

- [ ] **Step 5: Commit**

```bash
git add allowlist-spring-config/src/main/java/com/example/allowlist/config/AllowListStartupValidator.java \
        allowlist-spring-config/src/test/java/com/example/allowlist/config/AllowListStartupValidatorTest.java
git commit -m "feat(spring-config): add AllowListStartupValidator with AopUtils proxy-aware annotation scanning"
```

---

### Task 10: `AllowListSpringConfigConfiguration`

**Files:**
- Create: `allowlist-spring-config/src/main/java/com/example/allowlist/config/AllowListSpringConfigConfiguration.java`
- Create: `allowlist-spring-config/src/test/java/com/example/allowlist/config/AllowListSpringConfigConfigurationTest.java`

- [ ] **Step 1: Write failing tests**

```java
// allowlist-spring-config/src/test/java/com/example/allowlist/config/AllowListSpringConfigConfigurationTest.java
package com.example.allowlist.config;

import com.example.allowlist.core.AllowListRegistry;
import com.example.allowlist.spring.security.AllowListAuthorizationManager;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Import;

import static org.assertj.core.api.Assertions.assertThat;

class AllowListSpringConfigConfigurationTest {

    private final ApplicationContextRunner runner = new ApplicationContextRunner()
        .withUserConfiguration(AllowListSpringConfigConfiguration.class)
        .withPropertyValues("allowlist.lists.admins=alice");

    @Test
    void registersAllowListRegistryBean() {
        runner.run(context ->
            assertThat(context).hasSingleBean(AllowListRegistry.class));
    }

    @Test
    void registersAllowListAuthorizationManagerBean() {
        runner.run(context ->
            assertThat(context).hasSingleBean(AllowListAuthorizationManager.class));
    }

    @Test
    void registeredRegistryContainsConfiguredLists() {
        runner.run(context -> {
            AllowListRegistry registry = context.getBean(AllowListRegistry.class);
            assertThat(registry.isAllowed("admins", "alice")).isTrue();
            assertThat(registry.isAllowed("admins", "mallory")).isFalse();
        });
    }

    @Test
    void serviceCanOverrideAllowListRegistryBean() {
        AllowListRegistry customRegistry = (listName, subject) -> true; // always allows

        runner
            .withBean(AllowListRegistry.class, () -> customRegistry)
            .run(context -> {
                AllowListRegistry bean = context.getBean(AllowListRegistry.class);
                // Should be the custom one, not the auto-configured one
                assertThat(bean.isAllowed("anything", "anyone")).isTrue();
            });
    }
}
```

- [ ] **Step 2: Run to confirm failure**

```bash
./gradlew :allowlist-spring-config:test --tests "com.example.allowlist.config.AllowListSpringConfigConfigurationTest"
```

Expected: FAIL — `AllowListSpringConfigConfiguration` not found

- [ ] **Step 3: Create `AllowListSpringConfigConfiguration.java`**

```java
// allowlist-spring-config/src/main/java/com/example/allowlist/config/AllowListSpringConfigConfiguration.java
package com.example.allowlist.config;

import com.example.allowlist.core.AllowListRegistry;
import com.example.allowlist.spring.security.AllowListAuthorizationManager;
import com.example.allowlist.spring.security.AllowListMethodSecurityConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;

@Import(AllowListMethodSecurityConfiguration.class)
@EnableConfigurationProperties(AllowListProperties.class)
public class AllowListSpringConfigConfiguration {

    // Two variants: one with @RefreshScope (when spring-cloud-context is present),
    // one static (when it is not). Both @ConditionalOnMissingBean so services can override.

    @Bean
    @ConditionalOnMissingBean(AllowListRegistry.class)
    @org.springframework.boot.autoconfigure.condition.ConditionalOnMissingClass(
        "org.springframework.cloud.context.scope.refresh.RefreshScope")
    public AllowListRegistry allowListRegistryStatic(AllowListProperties props) {
        return AllowListRegistryFactory.create(props);
    }

    @Bean
    @ConditionalOnMissingBean(AllowListRegistry.class)
    @org.springframework.boot.autoconfigure.condition.ConditionalOnClass(
        name = "org.springframework.cloud.context.scope.refresh.RefreshScope")
    @org.springframework.cloud.context.config.annotation.RefreshScope
    public AllowListRegistry allowListRegistryRefreshable(AllowListProperties props) {
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

- [ ] **Step 4: Run all tests in the module**

```bash
./gradlew :allowlist-spring-config:test
```

Expected: `BUILD SUCCESSFUL`, all tests PASS

- [ ] **Step 5: Commit**

```bash
git add allowlist-spring-config/src/main/java/com/example/allowlist/config/AllowListSpringConfigConfiguration.java \
        allowlist-spring-config/src/test/java/com/example/allowlist/config/AllowListSpringConfigConfigurationTest.java
git commit -m "feat(spring-config): add AllowListSpringConfigConfiguration wiring beans with RefreshScope conditional"
```

---

## Chunk 5: Boot Starters and BOM

### Task 11: `AllowListBoot3AutoConfiguration`

**Files:**
- Create: `allowlist-spring-boot-starter-boot3/src/main/java/com/example/allowlist/boot3/AllowListBoot3AutoConfiguration.java`
- Create: `allowlist-spring-boot-starter-boot3/src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`
- Create: `allowlist-spring-boot-starter-boot3/src/test/java/com/example/allowlist/boot3/AllowListBoot3AutoConfigurationTest.java`

- [ ] **Step 1: Write failing autoconfiguration tests**

```java
// allowlist-spring-boot-starter-boot3/src/test/java/com/example/allowlist/boot3/AllowListBoot3AutoConfigurationTest.java
package com.example.allowlist.boot3;

import com.example.allowlist.core.AllowList;
import com.example.allowlist.core.AllowListRegistry;
import com.example.allowlist.spring.security.AllowListMisconfigurationException;
import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.security.authorization.method.AuthorizationManagerBeforeMethodInterceptor;

import static org.assertj.core.api.Assertions.assertThat;

class AllowListBoot3AutoConfigurationTest {

    private final ApplicationContextRunner runner = new ApplicationContextRunner()
        .withConfiguration(AutoConfigurations.of(AllowListBoot3AutoConfiguration.class));

    @Test
    void registersAllowListRegistryWhenListsConfigured() {
        runner
            .withPropertyValues("allowlist.lists.admins=alice,bob")
            .run(context -> assertThat(context).hasSingleBean(AllowListRegistry.class));
    }

    @Test
    void registersMethodInterceptor() {
        runner
            .withPropertyValues("allowlist.lists.admins=alice")
            .run(context ->
                assertThat(context).hasSingleBean(
                    AuthorizationManagerBeforeMethodInterceptor.class));
    }

    @Test
    void startupValidatorDetectsUnknownListAtStartup() {
        // Controller bean references a list that doesn't exist in config
        runner
            .withPropertyValues("allowlist.lists.admins=alice")
            .withBean("controller", BrokenController.class, BrokenController::new)
            .run(context -> {
                assertThat(context).hasFailed();
                assertThat(context.getStartupFailure())
                    .rootCause()
                    .isInstanceOf(AllowListMisconfigurationException.class)
                    .hasMessageContaining("nonexistent-list");
            });
    }

    @Test
    void doesNotRegisterJwtFilterChainByDefault() {
        runner
            .withPropertyValues("allowlist.lists.admins=alice")
            .run(context ->
                assertThat(context)
                    .doesNotHaveBean(org.springframework.security.web.SecurityFilterChain.class));
    }

    @Test
    void registersJwtFilterChainWhenOptedIn() {
        runner
            .withPropertyValues(
                "allowlist.lists.admins=alice",
                "allowlist.jwt.auto-configure=true",
                "spring.security.oauth2.resourceserver.jwt.issuer-uri=https://auth.example.com")
            .run(context ->
                assertThat(context)
                    .hasSingleBean(org.springframework.security.web.SecurityFilterChain.class));
    }

    static class BrokenController {
        @AllowList("nonexistent-list")
        public void someEndpoint() {}
    }
}
```

- [ ] **Step 2: Run to confirm failure**

```bash
./gradlew :allowlist-spring-boot-starter-boot3:test --tests "com.example.allowlist.boot3.AllowListBoot3AutoConfigurationTest"
```

Expected: FAIL — `AllowListBoot3AutoConfiguration` not found

- [ ] **Step 3: Create `AllowListBoot3AutoConfiguration.java`**

```java
// allowlist-spring-boot-starter-boot3/src/main/java/com/example/allowlist/boot3/AllowListBoot3AutoConfiguration.java
package com.example.allowlist.boot3;

import com.example.allowlist.config.AllowListSpringConfigConfiguration;
import com.example.allowlist.config.AllowListStartupValidator;
import com.example.allowlist.core.AllowListRegistry;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.autoconfigure.security.servlet.SecurityAutoConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;

// Run after Spring Security's own autoconfiguration so @ConditionalOnMissingBean
// for SecurityFilterChain resolves correctly.
@AutoConfiguration(after = SecurityAutoConfiguration.class)
@ConditionalOnClass(name = {
    "org.springframework.security.web.SecurityFilterChain",
    "com.example.allowlist.core.AllowListRegistry"
})
@Import(AllowListSpringConfigConfiguration.class)
// @EnableMethodSecurity activates Spring AOP method interception.
// It is idempotent when declared multiple times — Spring deduplicates it.
// CAVEAT: conflicts with @EnableMethodSecurity(prePostEnabled=false). In that
// case, exclude this autoconfiguration and declare @EnableMethodSecurity manually.
@EnableMethodSecurity
public class AllowListBoot3AutoConfiguration {

    // Registered HERE (not in AllowListSpringConfigConfiguration) because the
    // validator needs the full bean context to scan for @AllowList annotations.
    // That context is only available at the autoconfiguration layer.
    @Bean
    @ConditionalOnMissingBean(AllowListStartupValidator.class)
    public AllowListStartupValidator allowListStartupValidator(AllowListRegistry registry) {
        return new AllowListStartupValidator(registry);
    }

    // Opt-in JWT SecurityFilterChain — only registered when explicitly requested
    // AND no other SecurityFilterChain exists. Never activated by default.
    @Bean
    @ConditionalOnMissingBean(SecurityFilterChain.class)
    @ConditionalOnProperty(
        prefix = "allowlist.jwt", name = "auto-configure",
        havingValue = "true", matchIfMissing = false)
    public SecurityFilterChain allowListJwtFilterChain(HttpSecurity http) throws Exception {
        return http
            .authorizeHttpRequests(auth -> auth.anyRequest().authenticated())
            .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
            .build();
    }
}
```

- [ ] **Step 4: Create `AutoConfiguration.imports`**

```
# allowlist-spring-boot-starter-boot3/src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
com.example.allowlist.boot3.AllowListBoot3AutoConfiguration
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
./gradlew :allowlist-spring-boot-starter-boot3:test
```

Expected: `BUILD SUCCESSFUL`, all tests PASS

- [ ] **Step 6: Commit**

```bash
git add allowlist-spring-boot-starter-boot3/src/
git commit -m "feat(boot3-starter): add AllowListBoot3AutoConfiguration with @EnableMethodSecurity, startup validator, and opt-in JWT chain"
```

---

### Task 12: `AllowListBoot4AutoConfiguration`

**Files:**
- Create: `allowlist-spring-boot-starter-boot4/src/main/java/com/example/allowlist/boot4/AllowListBoot4AutoConfiguration.java`
- Create: `allowlist-spring-boot-starter-boot4/src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`
- Create: `allowlist-spring-boot-starter-boot4/src/test/java/com/example/allowlist/boot4/AllowListBoot4AutoConfigurationTest.java`

- [ ] **Step 1: Write failing test**

```java
// allowlist-spring-boot-starter-boot4/src/test/java/com/example/allowlist/boot4/AllowListBoot4AutoConfigurationTest.java
package com.example.allowlist.boot4;

import com.example.allowlist.core.AllowList;
import com.example.allowlist.core.AllowListRegistry;
import com.example.allowlist.spring.security.AllowListMisconfigurationException;
import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.security.authorization.method.AuthorizationManagerBeforeMethodInterceptor;

import static org.assertj.core.api.Assertions.assertThat;

class AllowListBoot4AutoConfigurationTest {

    private final ApplicationContextRunner runner = new ApplicationContextRunner()
        .withConfiguration(AutoConfigurations.of(AllowListBoot4AutoConfiguration.class));

    @Test
    void registersAllowListRegistry() {
        runner
            .withPropertyValues("allowlist.lists.admins=alice")
            .run(context -> assertThat(context).hasSingleBean(AllowListRegistry.class));
    }

    @Test
    void registersMethodInterceptor() {
        runner
            .withPropertyValues("allowlist.lists.admins=alice")
            .run(context ->
                assertThat(context).hasSingleBean(
                    AuthorizationManagerBeforeMethodInterceptor.class));
    }

    @Test
    void startupValidatorDetectsUnknownListAtStartup() {
        runner
            .withPropertyValues("allowlist.lists.admins=alice")
            .withBean("controller", BrokenController.class, BrokenController::new)
            .run(context -> {
                assertThat(context).hasFailed();
                assertThat(context.getStartupFailure())
                    .rootCause()
                    .isInstanceOf(AllowListMisconfigurationException.class)
                    .hasMessageContaining("nonexistent-list");
            });
    }

    @Test
    void doesNotRegisterJwtFilterChainByDefault() {
        runner
            .withPropertyValues("allowlist.lists.admins=alice")
            .run(context ->
                assertThat(context)
                    .doesNotHaveBean(org.springframework.security.web.SecurityFilterChain.class));
    }

    @Test
    void registersJwtFilterChainWhenOptedIn() {
        runner
            .withPropertyValues(
                "allowlist.lists.admins=alice",
                "allowlist.jwt.auto-configure=true",
                "spring.security.oauth2.resourceserver.jwt.issuer-uri=https://auth.example.com")
            .run(context ->
                assertThat(context)
                    .hasSingleBean(org.springframework.security.web.SecurityFilterChain.class));
    }

    static class BrokenController {
        @AllowList("nonexistent-list")
        public void someEndpoint() {}
    }
}
```

- [ ] **Step 2: Run to confirm failure**

```bash
./gradlew :allowlist-spring-boot-starter-boot4:test --tests "com.example.allowlist.boot4.AllowListBoot4AutoConfigurationTest"
```

Expected: FAIL — `AllowListBoot4AutoConfiguration` not found

- [ ] **Step 3: Create `AllowListBoot4AutoConfiguration.java`**

```java
// allowlist-spring-boot-starter-boot4/src/main/java/com/example/allowlist/boot4/AllowListBoot4AutoConfiguration.java
package com.example.allowlist.boot4;

import com.example.allowlist.config.AllowListSpringConfigConfiguration;
import com.example.allowlist.config.AllowListStartupValidator;
import com.example.allowlist.core.AllowListRegistry;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.autoconfigure.security.servlet.SecurityAutoConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;

// Initially a thin duplicate of AllowListBoot3AutoConfiguration.
// This class exists to isolate any Boot 4 / Security 7 API divergence.
// Update the JWT DSL here if Spring Security 7 introduces breaking changes.
@AutoConfiguration(after = SecurityAutoConfiguration.class)
@ConditionalOnClass(name = {
    "org.springframework.security.web.SecurityFilterChain",
    "com.example.allowlist.core.AllowListRegistry"
})
@Import(AllowListSpringConfigConfiguration.class)
@EnableMethodSecurity
public class AllowListBoot4AutoConfiguration {

    @Bean
    @ConditionalOnMissingBean(AllowListStartupValidator.class)
    public AllowListStartupValidator allowListStartupValidator(AllowListRegistry registry) {
        return new AllowListStartupValidator(registry);
    }

    @Bean
    @ConditionalOnMissingBean(SecurityFilterChain.class)
    @ConditionalOnProperty(
        prefix = "allowlist.jwt", name = "auto-configure",
        havingValue = "true", matchIfMissing = false)
    public SecurityFilterChain allowListJwtFilterChain(HttpSecurity http) throws Exception {
        return http
            .authorizeHttpRequests(auth -> auth.anyRequest().authenticated())
            .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
            .build();
    }
}
```

- [ ] **Step 4: Create `AutoConfiguration.imports` for boot4**

```
# allowlist-spring-boot-starter-boot4/src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
com.example.allowlist.boot4.AllowListBoot4AutoConfiguration
```

- [ ] **Step 5: Run tests**

```bash
./gradlew :allowlist-spring-boot-starter-boot4:test
```

Expected: `BUILD SUCCESSFUL`, all tests PASS

- [ ] **Step 6: Run the full build to confirm all modules pass together**

```bash
./gradlew build
```

Expected: `BUILD SUCCESSFUL`, all modules compile and test clean

- [ ] **Step 7: Commit**

```bash
git add allowlist-spring-boot-starter-boot4/src/
git commit -m "feat(boot4-starter): add AllowListBoot4AutoConfiguration as thin Boot 4 duplicate of Boot 3 starter"
```

---

### Task 13: End-to-end integration test

**Files:**
- Create: `allowlist-spring-boot-starter-boot3/src/test/java/com/example/allowlist/boot3/AllowListIntegrationTest.java`

This test proves the full stack works: a real controller annotated with `@AllowList`, a real JWT token (signed with a test key), and Spring MockMvc.

- [ ] **Step 1: Add `nimbus-jose-jwt` test dependency to boot3 starter for test JWT generation**

Append to `allowlist-spring-boot-starter-boot3/build.gradle.kts`:

```kotlin
    // JWT generation for integration tests only
    testImplementation("com.nimbusds:nimbus-jose-jwt:9.37.3")
```

- [ ] **Step 2: Write the failing integration test**

```java
// allowlist-spring-boot-starter-boot3/src/test/java/com/example/allowlist/boot3/AllowListIntegrationTest.java
package com.example.allowlist.boot3;

import com.example.allowlist.core.AllowList;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.Customizer;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.interfaces.RSAPublicKey;
import java.util.Date;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest(classes = AllowListIntegrationTest.TestApplication.class)
@AutoConfigureMockMvc
@TestPropertySource(properties = {
    "allowlist.lists.finance-admins=alice,bob"
})
class AllowListIntegrationTest {

    private static KeyPair keyPair;

    @BeforeAll
    static void generateKeyPair() throws Exception {
        KeyPairGenerator gen = KeyPairGenerator.getInstance("RSA");
        gen.initialize(2048);
        keyPair = gen.generateKeyPair();
    }

    @Autowired
    MockMvc mockMvc;

    private String jwtFor(String subject) throws Exception {
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
            .subject(subject)
            .issuer("test-issuer")
            .expirationTime(new Date(System.currentTimeMillis() + 60_000))
            .build();
        SignedJWT jwt = new SignedJWT(
            new JWSHeader(JWSAlgorithm.RS256),
            claims);
        jwt.sign(new RSASSASigner(keyPair.getPrivate()));
        return jwt.serialize();
    }

    @Test
    void allowsAccessForSubjectInList() throws Exception {
        mockMvc.perform(get("/finance/reports")
                .header("Authorization", "Bearer " + jwtFor("alice")))
            .andExpect(status().isOk());
    }

    @Test
    void deniesAccessForSubjectNotInList() throws Exception {
        mockMvc.perform(get("/finance/reports")
                .header("Authorization", "Bearer " + jwtFor("mallory")))
            .andExpect(status().isForbidden());
    }

    @Test
    void deniesAccessWithNoToken() throws Exception {
        mockMvc.perform(get("/finance/reports"))
            .andExpect(status().isUnauthorized());
    }

    @Test
    void unprotectedEndpointIsAccessible() throws Exception {
        mockMvc.perform(get("/health")
                .header("Authorization", "Bearer " + jwtFor("anyone")))
            .andExpect(status().isOk());
    }

    // Minimal Spring Boot application for integration testing
    @Configuration
    @org.springframework.boot.autoconfigure.SpringBootApplication
    static class TestApplication {

        // Provide a JwtDecoder backed by the test RSA key pair
        @Bean
        JwtDecoder jwtDecoder() {
            return NimbusJwtDecoder
                .withPublicKey((RSAPublicKey) keyPair.getPublic())
                .build();
        }

        @Bean
        SecurityFilterChain testSecurityChain(HttpSecurity http) throws Exception {
            return http
                .authorizeHttpRequests(auth -> auth.anyRequest().authenticated())
                .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
                .build();
        }
    }

    @RestController
    static class FinanceController {

        @GetMapping("/finance/reports")
        @AllowList("finance-admins")
        public String getReports() {
            return "reports";
        }

        @GetMapping("/health")
        public String health() {
            return "ok";
        }
    }
}
```

- [ ] **Step 3: Run to confirm failure**

```bash
./gradlew :allowlist-spring-boot-starter-boot3:test --tests "com.example.allowlist.boot3.AllowListIntegrationTest"
```

Expected: FAIL — compilation error (test app not found)

- [ ] **Step 4: Run tests to confirm they pass**

```bash
./gradlew :allowlist-spring-boot-starter-boot3:test --tests "com.example.allowlist.boot3.AllowListIntegrationTest"
```

Expected: `BUILD SUCCESSFUL`, all 4 integration tests PASS

- [ ] **Step 5: Run the full build one final time**

```bash
./gradlew build
```

Expected: `BUILD SUCCESSFUL`

- [ ] **Step 6: Commit**

```bash
git add allowlist-spring-boot-starter-boot3/src/test/java/com/example/allowlist/boot3/AllowListIntegrationTest.java \
        allowlist-spring-boot-starter-boot3/build.gradle.kts
git commit -m "test(boot3-starter): add end-to-end integration test covering allow, deny and unauthenticated paths"
```

---

### Task 14: CI compatibility matrix workflow

**Files:**
- Create: `.github/workflows/compatibility.yml`

- [ ] **Step 1: Create the CI workflow**

```yaml
# .github/workflows/compatibility.yml
name: Spring Boot Compatibility Matrix

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    name: Boot ${{ matrix.spring-boot-version }}
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        spring-boot-version:
          - "3.0.0"     # compile baseline — must pass
          - "3.0.13"    # latest 3.0.x patch
          - "3.1.12"
          - "3.2.10"
          - "3.3.5"
          - "3.4.1"

    steps:
      - uses: actions/checkout@v4

      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'

      - name: Setup Gradle
        uses: gradle/actions/setup-gradle@v3

      - name: Run tests against Boot ${{ matrix.spring-boot-version }}
        run: ./gradlew test -PspringBootVersion=${{ matrix.spring-boot-version }}

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results-boot-${{ matrix.spring-boot-version }}
          path: '**/build/reports/tests/'
```

- [ ] **Step 2: Verify workflow syntax**

```bash
# Requires GitHub CLI
gh workflow view .github/workflows/compatibility.yml 2>/dev/null || echo "Workflow file created — push to GitHub to validate"
```

- [ ] **Step 3: Commit**

```bash
mkdir -p .github/workflows
git add .github/workflows/compatibility.yml
git commit -m "ci: add Spring Boot compatibility matrix workflow testing Boot 3.0 through 3.4"
```

---

### Task 15: Final verification and tag

- [ ] **Step 1: Run the full build with explicit version override to simulate CI matrix**

```bash
./gradlew clean build -PspringBootVersion=3.0.0
./gradlew clean build -PspringBootVersion=3.4.1
```

Expected: `BUILD SUCCESSFUL` for both

- [ ] **Step 2: Verify all module JARs are produced**

```bash
find . -path "*/build/libs/*.jar" -not -name "*-plain.jar" | sort
```

Expected output (one JAR per module):
```
./allowlist-core/build/libs/allowlist-core-1.0.0-SNAPSHOT.jar
./allowlist-spring-security/build/libs/allowlist-spring-security-1.0.0-SNAPSHOT.jar
./allowlist-spring-config/build/libs/allowlist-spring-config-1.0.0-SNAPSHOT.jar
./allowlist-spring-boot-starter-boot3/build/libs/allowlist-spring-boot-starter-boot3-1.0.0-SNAPSHOT.jar
./allowlist-spring-boot-starter-boot4/build/libs/allowlist-spring-boot-starter-boot4-1.0.0-SNAPSHOT.jar
```

- [ ] **Step 3: Confirm the build is ready for release**

The library is now at `1.0.0-SNAPSHOT`. Do not tag SNAPSHOT versions — SNAPSHOT artifacts are mutable by convention and annotated tags imply a stable, immutable point.

When you are ready to cut a release:
1. Update `version` in `gradle.properties` to `1.0.0` (remove `-SNAPSHOT`)
2. Run `./gradlew build` one final time
3. Tag: `git tag -a v1.0.0 -m "Release 1.0.0"` and push the tag
4. Publish: `./gradlew publish`

---
