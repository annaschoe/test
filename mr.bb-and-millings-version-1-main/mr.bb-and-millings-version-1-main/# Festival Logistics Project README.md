# Festival Logistics Inventory Management System

A Flask-based web application for managing inventory and logistics between festival locations. This system allows festival staff to track, transfer, and manage inventory items across multiple festival venues.

## Project Overview

This application provides a robust solution for festival organizers to:
- Track inventory items across multiple locations
- Transfer items between locations with accountability
- Generate reports on current inventory status
- Manage user access with role-based permissions
- Export data for offline analysis

## Features

- **User Authentication**: Secure login and registration system with password hashing
- **Inventory Management**: Add, edit, delete, and search inventory items
- **Transfer System**: Send items between festival locations with tracking
- **Reporting**: Generate Excel reports of inventory and transfer history
- **Admin Dashboard**: Administrative controls for user and system management
- **Responsive Design**: Works on desktop and mobile devices for on-the-go management
- **Database Security**: Optimized SQLite configuration with proper access controls

## Technical Architecture

- **Backend**: Flask (Python)
- **Database**: SQLite with WAL journaling
- **Authentication**: Flask-Login
- **Security**: CSRF protection, password hashing, rate limiting
- **Frontend**: HTML, CSS, JavaScript
- **Reporting**: Excel export via openpyxl

## Setup Instructions

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd festival-logistics
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e .
   # or
   pip install -r requirements.txt
   ```

4. **Configure the application**
   - Create a `.env` file in the project root with the following variables:
     ```
     FLASK_APP=flask_app.app
     FLASK_DEBUG=False
     SECRET_KEY=your_secret_key_here
     ```

5. **Initialize the database**
   ```bash
   python -c "from flask_app.app import app, init_db; app.app_context().push(); init_db()"
   ```

6. **Run the application**
   ```bash
   python run.py
   ```
   Or alternatively:
   ```bash
   flask run --host=0.0.0.0
   ```

7. **Access the application**
   - From the same machine: http://localhost:5000
   - From other devices on the network: http://[your-ip-address]:5000

### Default Admin Account

The system creates a default admin account at initialization:
- Username: admin
- Password: admin_password

**IMPORTANT**: Change this password immediately after first login.

## Troubleshooting

If you encounter database access issues:
- Check file permissions on the database file
- Try running `python flask_app/debug_transfers.py` to view database status
- See `/debug` endpoint (only available in debug mode)

For connectivity issues:
- Try running `python minimal.py` to test basic server functionality
- Check firewall settings if accessing from other devices

## Development

To enable development mode:
```bash
export FLASK_DEBUG=True  # On Windows: set FLASK_DEBUG=True
python run.py
```

## Contribution Guidelines

Thank you for your interest in contributing to the Festival Logistics project! This document outlines the process for making contributions to help maintain quality and consistency.

### Getting Started

1. **Fork the repository** to your GitHub account
2. **Clone your fork** locally on your machine
3. **Create a new branch** for your contribution:
   ```bash
   git checkout -b feature/your-feature-name
   ```

### Development Environment

1. Set up your development environment following the setup instructions in the README
2. Activate the virtual environment before making changes
3. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

### Making Changes

1. **Keep changes focused** - Submit one feature or bug fix per pull request
2. **Follow coding style** - Match the existing code style (PEP 8 for Python)
3. **Add/update documentation** - Include docstrings and update README if needed
4. **Write meaningful commit messages** - Use clear, descriptive commit messages

### Testing

1. **Add tests** for new functionality
2. **Run the test suite** before submitting:
   ```bash
   pytest
   ```
3. **Check code quality** with linters:
   ```bash
   flake8 .
   ```

### Submitting Changes

1. **Push changes** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
2. **Create a pull request** against the `main` branch of the original repository
3. **Describe your changes** in the PR description:
   - What does this PR do?
   - Why is this change needed?
   - Any specific implementation details worth mentioning?
   - Include screenshots for UI changes

### Pull Request Review

1. Maintainers will review your PR as soon as possible
2. Address any requested changes or questions
3. Once approved, maintainers will merge your contribution

### Reporting Issues

1. Use the GitHub issue tracker to report bugs or suggest features
2. Provide clear details including:
   - Steps to reproduce bugs
   - Expected vs. actual behavior
   - Error messages and/or screenshots
   - Environment details (OS, browser version)

### Code of Conduct

- Be respectful and inclusive in all interactions
- Provide constructive feedback
- Focus on the code, not the person

Thank you for helping improve the Festival Logistics system!

## License

[Your license information here]

## Contact

[Your contact information here]