# Historical disaster data

This folder records the public historical disaster events used by the project.
The coordinates are used as representative impact-zone centers for a course-level
spatial overlay experiment. They are not claimed to be official road-closure
or street-level damage records.

Workflow:
1. AMap provides real route geometry, road names, distance, and traffic status.
2. Public historical disaster records provide event type, date, broad location, and evidence.
3. The project creates an influence buffer around the event impact center.
4. Road segments intersecting the buffer are marked as flood or collapse risk.