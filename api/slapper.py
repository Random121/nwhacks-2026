from serial import Serial


class Slapper:
    serial: Serial

    def __init__(self, port, baud):
        self.serial = Serial(port=port, baudrate=baud)

    def slap_user(self):
        self.serial.write(b"F")
