# Type can support parameter source precedence

We want typer commands to allow parameters to be specified from multiple sources, such as command line arguments, environment variables, and configuration files, but with a fixed precedence.

> Typer Flags -> Env Variables -> Config Files -> Code Defaults

## How to achieve this
 
- Use [typer](https://typer.tiangolo.com/) and add annotated to the parameter e.g. ```typer.Option(envvar="<ENV_VAR_NAME>")``` to allow override by env var
- Then combine with [typer-config](https://github.com/typer-orm/typer-config) to allow override by config file (yaml, toml)
- The @use_xxxx_config decorator also has a `config_file` parameter to specify the default name of the config file so it doesn't need to be specified as a command line argument.

Bringing it all together:

``` python
from typing import Annotated
import typer
from typer_config import use_toml_config  # Installs via pip install typer-config

app = typer.Typer()

@app.command()
@use_toml_config()  # Adds a --config option automatically
def main(
user: Annotated[str, typer.Option(envvar="APP_USER")] = "default_guest",
port: int = 8080
):
# Precedence validation logic order:
# 1. Did user pass --user CLI flag? If yes, use it.
# 2. Is APP_USER set in the environment? If yes, use it.
# 3. Is 'user' specified in the --config TOML file? If yes, use it.
# 4. Fall back to "default_guest".
typer.echo(f"User: {user}, Port: {port}")

if __name__ == "__main__":
app()
```
 
