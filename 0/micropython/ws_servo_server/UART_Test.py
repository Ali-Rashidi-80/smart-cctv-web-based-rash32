from machine import UART, Pin
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))
uart.write("P\n")