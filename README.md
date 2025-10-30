# REST-API
This repository includes the documentation and some exemplary source code for the setup and operation of the getAir REST-API.

The content provided in this repository is free to be used by everybody with the respective knowledge about fundamental REST-API principles and command line tools. Fundamental knowledge about JSON, objects and data types is reqired.

getAir does NOT provide any service or warranty for the content provided! We assume no liability for any damage caused by the provided content!
Furthermore, we make no claim to update this documentation in case of system updates - and thereby arising incompatibilities - or security holes.

Please especially pay attention to the information provided in the documentation regarding:
- Target audience
- Device compatibility
- Prerequisites
- Important notes


## Setup
Follow these steps to set up the project locally:
1. Clone the repository

git clone https://github.com/getaireu/REST-API
cd REST-API

2. Create and activate a virtual environment
On Linux / macOS:

python3 -m venv venv

source venv/bin/activate

On Windows (CMD):

python -m venv venv
venv\Scripts\activate

On Windows (PowerShell):

python -m venv venv
.\venv\Scripts\Activate.ps1

3. Install dependencies

pip install -r requirements.txt

4. Rename the file .credentials.template to .credentials and insert your email and passphrase
