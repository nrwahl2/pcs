import os
import tempfile


def generate_binary_key(random_bytes_count):
    return os.urandom(random_bytes_count)

def environment_file_to_dict(config):
    """
    Parse systemd Environment file. This parser is simplified version of
    parser in systemd, because of their poor implementation.
    Returns configuration in dictionary in format:
    {
        <option>: <value>,
        ...
    }

    config -- Environment file as string
    """
    # escape new lines
    config = config.replace("\\\n", "")

    data = {}
    for line in [l.strip() for l in config.split("\n")]:
        if line == "" or line.startswith("#") or line.startswith(";"):
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        value = val.strip()
        data[key.strip()] = value
    return data

def dict_to_environment_file(config_dict):
    """
    Convert data in dictionary to Environment file format.
    Returns Environment file as string in format:
    # comment
    <option>=<value>
    ...

    config_dict -- dictionary in format: { <option>: <value>, ...}
    """
    lines = ["# This file has been generated by pcs.\n"]
    for key, val in sorted(config_dict.items()):
        lines.append("{key}={val}\n".format(key=key, val=val))
    return "".join(lines)

def write_tmpfile(data, binary=False):
    """
    Write data to a new tmp file and return the file; raises EnvironmentError.

    string or bytes data -- data to write to the file
    bool binary -- treat data as binary?
    """
    mode = "w+b" if binary else "w+"
    tmpfile = tempfile.NamedTemporaryFile(mode=mode, suffix=".pcs")
    tmpfile.write(data)
    tmpfile.flush()
    return tmpfile
