import launch

# ruamel.yaml writes edited EPS prompts back to the YAML files while keeping comments and block styles.
if not launch.is_installed("ruamel.yaml"):
    launch.run_pip("install ruamel.yaml", "ruamel.yaml for Visual EPS")
