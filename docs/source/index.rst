#########################
USO: User Services Online
#########################

The User Services Online (USO) is an information management system developed at
the Canadian Light Source which manages all information related to the use of a
large-scale scientific research facility such as a synchrotron. A customized variant
of this software is deployed and actively used at the Canadian Light Source, Inc (CLSI).
However, this documentation describes only the open-source version of USO, which is available
for use by other facilities. For specific documentation on the CLSI version, please refer to the
CLSI User Portal documentation.

.. note::

    Please cite our publication on the software if you use it in your work:

    * Design and implementation of a user office system for the Canadian Light Source
      K Janzen, M Fodje - Synchrotron Radiation (2025), Vol 32, Part 2
      https://doi.org/10.1107/S1600577525000153


How to Use This Documentation
-----------------------------
This documentation is divided into sections targeted at different audiences. After the
:ref:`Introduction <introduction>`, you can skip to the section that is most relevant to you:
the :ref:`User Guide<user-guide>` is for facility users (scientists, researchers) who
will interact with the USO system to manage their proposals and experiments; :ref:`Staff Guide<staff-guide>`
is for User Office staff and other facility staff who manage specific instruments or beamlines.
The :ref:`Administrator Guide<admin-guide>` is for system administrators responsible for deploying,
configuring, and maintaining the USO instance. The :ref:`Developer Guide <dev-guide>` is for developers
who want to extend or customize the USO system.


.. toctree::
   :maxdepth: 1
   :caption: Introduction

   introduction/index

.. toctree::
   :maxdepth: 1
   :caption: User Guide

   user_guide/index

.. toctree::
   :maxdepth: 1
   :caption: Staff Guide

   staff_guide/index

.. toctree::
   :maxdepth: 1
   :caption: Administrator Guide

   admin_guide/index

.. toctree::
   :maxdepth: 1
   :caption: Developer Guide

   dev_guide/index


