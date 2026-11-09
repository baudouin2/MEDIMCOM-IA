"""The tests never use the base built on the machine (base_v2): identical results everywhere."""
import os

os.environ["MEDIMCOM_BASE"] = "aucune"
