"""Mission registry. A mission module exposes build() -> Session.

To add a mission: create a module here that builds a Device, its Networks
and a Mission, returns a Session, and register it below.
"""

from hacking.missions import corporate_archive, procedural, unsent_message

MISSIONS = {
    "corporate_archive": corporate_archive.build,
    "unsent_message": unsent_message.build,
}
DEFAULT = "corporate_archive"


def build(mission_id=DEFAULT):
    if procedural.is_job(mission_id):
        return procedural.build(mission_id)
    return MISSIONS[mission_id]()
