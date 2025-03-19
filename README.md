# python-smu4000

python-smu4000 is a Python library for controlling an Ark Metrica Ltd. SMU-4000
source-measure unit (SMU).

## Installation

The easiest way to get started with this library is to install the latest version from
GitHub using pip as follows:

```sh
pip install git+https://github.com/ark-metrica/python-smu4000.git
```

## Usage

This library provides an object for controlling individual SMU channels, as if each
channel is a discrete SMU. An SMU channel object can be invoked in a context manager
to handle automatic connection and disconnection of the communication interface.
For example, to connect to channel 1 and print its identity string you could do the
following:

```python
import smu4000

HOST = "192.168.0.10"  # IP address or host name
PORT = 50001  # port corresponding to channel 1 in this example
TIMEOUT = 3  # seconds

# the context manager will automatically connect to the SMU upon instantiation, and
# turn off the output and disconnect upon completion
with smu4000.Smu4000(HOST, PORT, TIMEOUT) as smu:
    print(smu.idn)

```

The SMU channel object allows the user to set the parameters of the SMU channel as
attributes, and configure measurements and acquire data using methods. For example:

```python
with smu4000.Smu4000(HOST, PORT, TIMEOUT) as smu:
    print(smu.idn)

    # set nplc
    smu.nplc = 1

    # configure the source for a DC measurement
    smu.configure_dc(
        source_function="volt",
        source_value=1.0,
        compliance=0.1,
    )

    # enable the output
    smu.output_enabled = True

    # perform the measurement
    data = smu.measure()

    # disable the output
    smu.output_enabled = False

    print(data)
```

Manually handling the connection and disconnection of the communication interface can
be achieved as follows:

```python
import smu4000

HOST = "192.168.0.10"
PORT = 50001
TIMEOUT = 3

smu = smu4000.Smu4000(HOST, PORT, TIMEOUT)
smu.connect()
print(smu.idn)
smu.disconnect()
```

Note that the `smu` object was instantiated with one PORT corresponding to one channel
on the instrument. Controlling multiple channels requires instantiation of one object
per channel, each with a unique port corresponding to the required channel. For example,
one way to control both channels 1 and 2 could be:

```python
import smu4000

HOST = "192.168.0.10"
PORT_CH1 = 50001
PORT_CH2 = 50002
TIMEOUT = 3

# create an object to control channel 1
smu_ch1 = smu4000.Smu4000(HOST, PORT_CH1, TIMEOUT)

# create an object to control channel 2
smu_ch2 = smu4000.Smu4000(HOST, PORT_CH2, TIMEOUT)

# connect to both channels
smu_ch1.connect()
smu_ch2.connect()

# print their id strings
print(f"Channel {smu_ch1.channel} identity: {smu_ch1.idn}")
print(f"Channel {smu_ch2.channel} identity: {smu_ch2.idn}")

# disconnect from both channels
smu_ch1.disconnect()
smu_ch2.disconnect()
```

See the `examples` folder for some more example use cases with greater detail.
