"""Les tests n'utilisent jamais la base constituée sur la machine (base_v2) : résultats identiques partout."""
import os

os.environ["MEDIMCOM_BASE"] = "aucune"
