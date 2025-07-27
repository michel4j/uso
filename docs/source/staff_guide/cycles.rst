
Managing Cycles
===============

The USO system operates on a cycle-based model. Each cycle is a defined period during which experiments can be
scheduled and performed. Cycles also include information about dates of activities that happen prior to the
start of the cycle, such as calls for proposals, reviews and allocation. By default there are two 6-month cycles per
year. However, different cycle types can be created, with customized options dates and durations. The management of
cycles is crucial for organizing the proposal submission, review, and allocation processes. This section provides an
overview of how cycles are managed within the USO system.

Cycle Types
----------------
Cycles are defined by their type, which determines the state date within the year, duration in months, and other
details such as, how early to open the call, the duration of the call, the duration of the review period, etc.

In essence, a cycle type defines the parameters for a calculating the dates for new Cycles. The cycle type
encapsulates the period of the year during which the derived cycle is active. For two 6-month cycles
per year, define two cycle types, one for each cycle, each with a 6-month duration. For a single cycle per year,
define one cycle type, with a duration of 12 months. For a single cycle every two years, define one cycle
type with a duration of 24 months.

.. note::
   Only one cycle of a given type can start in a given year, and no two cycles of the same type can overlap.
   The duration of a cycle should not be confused with the duration of a project. Projects can be valid for multiple
   cycles.


Creating a Cycle
----------------
Cycles are created automatically by the system based on the defined cycle schedule. However, User Office Administrators
can create new cycles manually if needed.


Viewing Cycles
----------------
To view the list of cycles, navigate to the :menuselection:`Proposals --> All Cycles` section of the USO system menu.
This will display a list of all cycles, including their start and end dates. Select a cycle from the list to access
the Cycle details page.  The current cycle is also available through :menuselection:`Proposals -> Current Cycle`.


Cycle Details
----------------
The Cycle details page provides comprehensive information about the selected cycle, including its start and end dates,

