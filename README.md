# Smart City Traveller 🌍

A web-based travel application designed to help users explore destinations, discover places of interest, and plan their travel experiences using location-based services.

## 📌 About the Project

**Smart City Traveller** is a Flask-based web application developed as a BCA final-year project. It integrates mapping and location-based APIs to support travel exploration and trip planning.

The project combines a Python backend with a web interface built using HTML, CSS, and JavaScript.

## ✨ Features

- **Interactive Maps:** Map-related functionality powered by the Google Maps API.
- **Place Discovery:** Location and place-related integration using the Foursquare API.
- **User Authentication:** Login and registration interfaces.
- **Travel Scheduling:** Interfaces for creating and managing travel schedules.
- **Dashboard:** A dedicated dashboard for accessing application features.
- **User Profile:** A profile interface for user-related information.
- **Feedback:** A page for submitting feedback.
- **Notifications:** A dedicated notifications interface.

*Note: The features listed above are based on the project's current file structure. Confirm their actual functionality before presenting them as fully implemented.*

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend development |
| Flask | Web application framework |
| HTML5 | Page structure |
| CSS3 | Styling and layout |
| JavaScript | Client-side functionality |
| Google Maps API | Mapping integration |
| Foursquare API | Place and location discovery |
| Firebase | Authentication or backend services, where configured |

## 📁 Project Structure

```text
smart-city-traveller/
├── app.py
├── requirements.txt
├── functions/
│   └── index.js
├── static/
│   ├── css/
│   │   └── styles.css
│   └── js/
│       ├── auth.js
│       ├── map.js
│       ├── schedule.js
│       └── utils.js
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── login.html
│   ├── signup.html
│   ├── dashboard.html
│   ├── map_view.html
│   └── ...
└── README.md
```

## ⚙️ Installation and Setup

### Prerequisites

- Python 3 installed
- Git installed
- Visual Studio Code or another code editor

### 1. Clone the repository

```bash
git clone https://github.com/kvrao16/smart-city-traveller.git
```

### 2. Navigate to the project directory

```bash
cd smart-city-traveller
```

### 3. Create a virtual environment

```bash
python -m venv venv
```

Activate it on Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

Create a local `.env` file for the API keys and configuration required by the application. Use the variable names expected by your code.

**Never upload your `.env` file or Firebase Admin SDK credentials to GitHub.**

### 6. Run the application

```bash
python app.py
```

Open the local URL displayed in the terminal. For a typical Flask development setup, this may be `http://127.0.0.1:5000`.

## 🔐 Security

- Keep API keys and private credentials out of source control.
- Store secrets in environment variables.
- Restrict API keys to the required services and authorized domains where applicable.
- Do not use production credentials in public repositories.

## 🎯 Project Objective

The objective of Smart City Traveller is to explore how web technologies, mapping APIs, and location-based services can be combined to create a convenient travel-planning experience.

## 👨‍💻 Developer

**Keerthivardhan K Rao**

- GitHub: [@kvrao16](https://github.com/kvrao16)
- Project Repository: [Smart City Traveller](https://github.com/kvrao16/smart-city-traveller)

## 📄 License

No license has been specified yet. Add a suitable license if you decide to distribute the project for reuse.
