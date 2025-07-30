.. _dev-guide:

System Architecture
===================

The USO (User Office System) is built using modern web technologies and follows a modular architecture to ensure
flexibility and scalability. The key technologies used in the USO system include:

- **Django**: A high-level Python web framework that encourages rapid development and clean, pragmatic design.
- **PostgreSQL**: An advanced, open-source relational database system that provides robust data storage.
- **Docker/Podman**: A platform for developing, shipping, and running applications in containers, ensuring consistency
  across different environments. Other containerization environments can be used as well.

The system is designed as a collection of integrated Django applications, each responsible for a specific aspect of
the User Office operations. This modular approach allows for easier maintenance and development of new features.
The included applications are:

- **agreements**: Manages user agreements
- **beamlines**: Manages beamlines, facilities and laboratories
- **isocron**: Manages background tasks
- **misc**: Contains miscellaneous utilities and functions used by other applications
- **notifier**: Handles notifications and alerts within the system
- **proposals**: Manages proposals, cycles, techniques and reviews
- **projects**: Manages projects, including materials, sessions, and handovers
- **publications**: Manages research publications
- **roleperms**: Handles the role-based access control system
- **samples**: Handles sample management, hazards, and contains a hazardous materials database
- **scheduler**: Manages the scheduling
- **surveys**: Manages surveys and user feedback
- **users**: Manages user accounts, registration, institutions and user addresses
- **weather**: Provides weather information

In addition, several packages we originally developed as part of the USO system have since been released as separate
open-source projects and are still used as external dependencies. These packages are documented separately. They are:

- `django-itemlist <https://github.com/michel4j/django-itemlist>`__: A reusable Django application for managing
  searchable/filterable lists of items. This is used by all list pages in the USO system.
- `django-dynforms <https://github.com/michel4j/django-dynforms>`__: A reusable Django application for designing
  forms. This is use for creating and managing forms in the USO system, including proposal submission forms, review
  forms, and survey forms.
- `django-crisp-modals <https://pypi.org/project/django-crisp-modals>`__: A reusable Django application
  for creating responsive modal forms in web applications using Bootstrap 5. This is the backend for all modal
  forms in the USO system.
- `django-reportcraft <https://michel4j.github.io/django-reportcraft/>`__: A reusable Django application
  for designing and generating reports. The application was not part of the original USO system, but was developed
  by using the same principles and was recently integrated into the USO system.

Other dependencies are listed in the `requirements.txt` file in the root of the repository.

Software Stack
--------------
As already mentioned, the backend of the USO system is built using Django, a high-level Python web framework. The
frontend is built using HTML, CSS, and JavaScript, with Bootstrap 5 for responsive design. The JavaScript framework
jQuery is used for DOM manipulation and AJAX requests. All JavaScript files are minified before inclusion in HTML files.
We use the `uglifyjs` command-line tool to minify JavaScript files.

For styling, we use SCSS (Sassy CSS), which is a preprocessor that extends CSS with features like variables, nested
rules, and mixins and is complied to minified CSS files before including them in the HTML pages. We use the `sassc`
command-line tool to compile SCSS files into CSS files.


