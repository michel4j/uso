.. _staff-guide:

Roles
=====
The USO system allows a variety of staff to interact with the system. The level of access, responsibilities and the
features exposed to each person accessing the system, is determined by their roles. Some roles are facility dependent
and apply only to the beamline instrument or sector to which it is assigned. Depending on the configuration of the
system, facility-specific roles may also expand to sub-units or instruments that are children of the facility, or in
some cases to parent facilities.

Roles can be qualified with a "Realm", which is identifies a specific functional unit or domain. This allows for
more granular control over access and responsibilities. For example, a person may have a role as a "Staff" member
on one beamline, allowing elevated privileges to manage that beamline only. However, on a different beamline outside
their "Realm", they would be a regular staff member with no special privileges.

The following roles are recognized in the system:

- **User**: A registered user of the system who can submit proposals, view their projects, and participate in sessions.
- **Staff**: A general staff. Staff members have access to view more information than regular users, and depending on
  their realm, they may have additional privileges and responsibilities.
- **Beamline Staff**: This role is just a qualified Staff role on a specific beamline or instrument.  Responsible for
  operating the beamline and providing user support. They can perform hand-overs,
  sign-offs, and manage sessions. Beamline staff can also view detailed information about beamline projects and the
  beamline's schedule.
- **Beamline Administrator**: A senior beamline staff member responsible for overseeing the beamline operations. They can
  manage beamline specifications, and techniques on the beamline. They can also schedule beam time, user support,
  and perform allocations.
- **Beamline Reviewer**: Responsible for providing technical review of proposals requesting access to the facility.
- **Health & Safety Staff**: Responsible for ensuring that all safety protocols are followed. They can review project
  materials and samples, and approve or reject them based on safety compliance.
- **Safety Approver**: A senior Health and Safety staff member who is responsible for assigning safety reviews
  and issuing final approval of project materials.
- **Reviewer**: Responsible for performing scientific review of proposals.
- **Beam Team Member**: A member of the Beam Team on a specific beamline/instrument. The Beam Team member may have
  the possibility of accessing privileged Access Pools on the beamline/instrument during proposal submission. This role,
  has no special privileges outside of the beamline/instrument realm.
- **User Office Administrator**: Responsible for managing all aspects of the user office system, user profiles,
  facilities, cycles, review tracks, etc. They can perform all administrative tasks and have access to all
  features of the system.


User Office Administrators can assign a limited set of roles to individuals through the their user profile. Other roles
are populated from an external source through an application programming interface (API).