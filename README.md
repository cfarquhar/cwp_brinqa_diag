- [Intro](#intro)
- [Setup](#setup)
  - [Clone repo](#clone-repo)
  - [Set up environment](#set-up-environment)
  - [Collect & set configuration items](#collect--set-configuration-items)
    - [CWP console path](#cwp-console-path)
    - [CWP access key](#cwp-access-key)
- [Run script](#run-script)

# Intro

This script collects CWP API performance data for troubleshooting a specific
issue.  It is "throwaway" code and does not include test cases, is not optimized
or elegant, and is not intended to be reused for other purposes.

# Setup

## Clone repo

```
git clone https://github.com/cfarquhar/cwp_brinqa_diag
```

## Set up environment

Exact steps will vary depending on what you use to manage python versions and
virtual environments.  This works for `pyenv` and `poetry`:

```
cd cwp_brinqa_diag
pyenv install 3.10.0
pyenv local 3.10.0
poetry install
poetry shell
```

If you are not using `poetry`, install the dependencies as shown below after
activating your virtualenv:

```
cd cwp_brinqa_diag
pip install -r requirements.txt
```

## Collect & set configuration items

### CWP console path
1. Log in to SaaS console
2. Navigate to Compute > System > Utilities
3. In the "Path to Console" section, copy the value
4. Create `CWP_CONSOLE_PATH` environment variable with this value:

```
# export CWP_CONSOLE_PATH=<CONSOLE_PATH>
```

### CWP access key

If you already have access keys created, configure them in the environment
variables as shown below.

1. Log in to SaaS console
2. Navigate to Settings > Access Keys
3. Click "Add Access Key" in the top right
4. Enter a name and expiration time (if desired)
5. Click "Create"
6. Copy the "Access Key ID" and "Secret Key" values
7. Create `CWP_USER` and `CWP_PASSWORD` environment variables with these values:

```
# export CWP_USER=<ACCESS_KEY_ID>
# export CWP_PASSWORD=<SECRET_KEY>
```

# Run script

```
python ./diag.py | tee summary-$(date +%s).txt
```

This will output a summary text file and a details csv file.  Please share both for analysis.