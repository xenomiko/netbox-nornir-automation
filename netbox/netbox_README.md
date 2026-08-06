# NetBox Bootstrap Automation

## Overview

I built this project to automate the initial population of a NetBox instance. Instead of manually creating sites, devices, interfaces, IP addresses, and cables through the web interface, I describe my infrastructure in a YAML file and let the script synchronize everything automatically.

The project uses the NetBox REST API through Pynetbox and is designed to be idempotent, meaning it can be run multiple times without creating duplicate objects.

## Features

* Create and update Sites
* Create and update Manufacturers
* Create and update Device Roles
* Create and update Device Types
* Create and update Devices
* Create Config Contexts
* Create Interfaces
* Assign IP Addresses
* Create Cables
* Validate data using Pydantic
* YAML-based Source of Truth

## Project Structure

* `main.py` – Orchestrates the synchronization process.
* `netbox_services.py` – Contains NetBox API and synchronization logic.
* `schemas.py` – Pydantic models used for data validation.
* `netbox.yaml` – Source of Truth describing the lab.

## Installation

```bash
pip install pynetbox pydantic pyyaml python-dotenv
```

Create a `.env` file:

```env
NB_URL=http://localhost:8000
NB_TOKEN=your_api_token
```

## Usage

```bash
python main.py
```

The script validates the data, resolves object relationships, and synchronizes the NetBox inventory.

## What I Learned

This project helped me gain hands-on experience with:

* REST API automation
* NetBox as a Source of Truth
* Data validation with Pydantic
* Idempotent automation design
* Building reusable Python code

## Next Steps

This project is the first stage of a larger network automation workflow. The next phase is integrating NetBox with Nornir and HashiCorp Vault to automate network operations using a Source of Truth driven approach.
