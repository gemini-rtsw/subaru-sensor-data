import subprocess
import sys
import os

# Set up EPICS environment for localhost
os.environ['EPICS_CA_ADDR_LIST'] = 'localhost'
os.environ['EPICS_CA_AUTO_ADDR_LIST'] = 'NO'

try:
    import epics
except ImportError:
    print("Error: pyepics library not found.")
    print("Please install it using: pip install pyepics")
    sys.exit(1)


def caget(pv_name):
    """Uses pyepics.caget to get the value of a given PV name."""
    try:
        # Use pyepics caget
        value = epics.caget(pv_name, timeout=5)
        if value is None:
            return f"Error: caget for {pv_name} timed out or PV not found."
        # Format output similar to command-line caget (PV name   value)
        # pyepics already includes the PV name if 'as_string' is True,
        # but let's keep the format explicit for clarity here.
        return f"{pv_name}    {value}"
    except Exception as e:
        # Catch potential Channel Access or other pyepics exceptions
        return f"An error occurred for {pv_name}: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_epics_pvs.py <PV_NAME_1> [PV_NAME_2] ...")
        sys.exit(1)

    pv_names = sys.argv[1:]

    for pv in pv_names:
        print(f"Querying PV: {pv}")
        output = caget(pv)
        print(f"Result: {output}\n") 