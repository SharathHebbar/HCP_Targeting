# HCP Targeting using system 1 Model - Laya

## Project Setup

### UV backbone

#### Install uv

#### Initialize the project

```sh
uv init 
```

#### Create a venv

```sh
uv venv
```

#### To activate the venv
```sh
source .venv/bin/activate
```

#### Install dependencies
```sh
uv sync
```

- Ensure you have `pyproject.toml`


## To get started

### Run the below code to generate HCP data
```sh
python synthetic_data_generation.py
``` 

### To Run the App

```sh
streamlit run app.py
```

## App Screenshots

### HCP 360 Page

![HCP 360 Page](assets/01_hcp_360_page.png)

### Targeting Console

![Console 1](assets/02_targeting_console.png)
![Console 2](assets/03_targeting_console.png)
![Console 3](assets/04_targeting_console.png)

### Advance Analytics

![Advance Analytics](assets/05_advance_analytics.png)