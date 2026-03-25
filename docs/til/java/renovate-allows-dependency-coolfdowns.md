# Renovate allows dependency cooldowns

 [Dependency cooldowns](https://blog.yossarian.net/2025/11/21/We-should-all-be-using-dependency-cooldowns) involve delaying updates of dependencies for a period of time, ensuring that there is time for supply chain attacks to be detected and fixed.
Renovate supports this feature through it's [minimum release age](https://docs.renovatebot.com/key-concepts/minimum-release-age/) configuration.

## How It Works

> minimumReleaseAge is a feature that requires Renovate to wait for a specified amount of time before suggesting a dependency update.

The renovate documentation explains exactly how this works and how to configure it. Note that as well as renovate some pacakge managers also support minimum release age. Need to check the interoperation with maven and gradle.  

## References

[Renovate - Mimimum Release Age](https://docs.renovatebot.com/key-concepts/minimum-release-age/)
 
