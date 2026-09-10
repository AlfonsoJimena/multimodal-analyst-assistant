import sys, tty, termios

# The getch method can determine which key has been pressed
# by the user on the keyboard by accessing the system files
# It will then return the pressed key as a variable
def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


#import curses
#init the curses screen
#stdscr = curses.initscr()
#use cbreak to not require a return key press
#curses.cbreak()
print "press q to quit"
quit=False
# loop
while quit !=True:
	#c = stdscr.getch()
	c = getch()
	#print curses.keyname(c),
	#if curses.keyname(c)=="q" :
	if (c == "q"):
		quit=True
	elif (c == "w"):
		print "It works!!!"

#curses.endwin()
