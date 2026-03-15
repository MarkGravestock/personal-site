---
date: 2026-03-15
tags:
  - networking
  - dns
---

# DNS TTL Controls How Long Resolvers Cache Records

When you update a DNS record, the change doesn't propagate instantly — resolvers
around the world keep serving the old value until the TTL (Time To Live) expires.

## How It Works

Every DNS record has a TTL value in seconds. When a resolver fetches a record,
it caches it for that many seconds before checking again. A TTL of `3600` means
any resolver that looked up your domain in the last hour may still be serving
the old IP — regardless of what you've set at your registrar.

```bash
# Check a record's TTL with dig
dig +noall +answer markgravestock.github.io

# Output includes TTL in the second column:
# markgravestock.github.io. 3600 IN A 185.199.108.153
```

**Practical implication:** If you're planning a migration, lower the TTL to
something like `300` (5 minutes) *at least one TTL period before the change*.
That way, after you update the record, propagation is fast.

## References

- [RFC 1035 — Domain Names: Implementation and Specification](https://datatracker.ietf.org/doc/html/rfc1035)
- [DNS TTL — Cloudflare Learning](https://www.cloudflare.com/learning/dns/glossary/dns-ttl/)
