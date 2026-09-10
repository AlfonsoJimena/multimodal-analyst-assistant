import threading
import traceback
import time
import numpy as np

item = 0
value = 0
stop = 0
count = 0

WINDOW_SIZE = 200
MAX_ITEMS_BUFFER = 50

#WINDOW_SIZE = 4
#MAX_ITEMS_BUFFER = 2



NUM_BUFFERS = 4
NUM_BUFFERS_WINDOW = WINDOW_SIZE / MAX_ITEMS_BUFFER

if NUM_BUFFERS_WINDOW > NUM_BUFFERS:
    print "\n[ERROR!!!][NUM_BUFFERS_WINDOW (" + str(NUM_BUFFERS_WINDOW) + ") > NUM_BUFFERS (" + str(NUM_BUFFERS) + ")!!!]\n"
    exit(0)

AccX_bufferArray = np.zeros((NUM_BUFFERS, MAX_ITEMS_BUFFER), dtype=float)
AccY_bufferArray = np.zeros((NUM_BUFFERS, MAX_ITEMS_BUFFER), dtype=float)
AccZ_bufferArray = np.zeros((NUM_BUFFERS, MAX_ITEMS_BUFFER), dtype=float)

AccXarray = np.zeros(WINDOW_SIZE, dtype=float)
AccYarray = np.zeros(WINDOW_SIZE, dtype=float)
AccZarray = np.zeros(WINDOW_SIZE, dtype=float)

p_recording_buffer = 0
p_item_in_recording_buffer = 0
p_processing_buffer = -1

num_buffers_recorded = 0
num_items_recorded = 0

stop_lock = threading.Lock()
count_lock = threading.Lock()

# represents the addition of an item to a resource
condition = threading.Condition()

def do_every (interval, worker_func, iterations = 0):
    global stop
    #print(stop)
    if stop == 0:
        if iterations != 1:
            timer = threading.Timer (
                interval,
                do_every, 
                [interval, worker_func, 0 if iterations == 0 else iterations-1]
                ).start ()
        worker_func ()
    else:
        print "\n[STOP PERIODICAL TASK]\n"
    

def print_hw ():
  print "hello world"

def print_so ():
  print "stackoverflow"
  
def ReadAccelerometer ():
    global AccX_bufferArray
    global AccY_bufferArray
    global AccZ_bufferArray    
    global AccXarray
    global AccYarray
    global AccZarray
    global p_recording_buffer
    global p_item_in_recording_buffer
    global count
    global item
    global num_buffers_recorded
    global num_items_recorded
    global p_processing_buffer

    count_lock.acquire()
    try:
        count = count + 1 # access shared resource
        
        num_items_recorded = num_items_recorded + 1
        
        AccX_bufferArray[p_recording_buffer, p_item_in_recording_buffer] = count
        AccY_bufferArray[p_recording_buffer, p_item_in_recording_buffer] = count
        AccZ_bufferArray[p_recording_buffer, p_item_in_recording_buffer] = count
        
        p_item_in_recording_buffer = p_item_in_recording_buffer + 1
        
        if p_item_in_recording_buffer >= MAX_ITEMS_BUFFER:
            # Se ha agotado el buffer actual...

            # se incrementa el numero de buffers grabados ...
            num_buffers_recorded = num_buffers_recorded + 1

            # y pasamos al siguiente buffer
            p_item_in_recording_buffer = 0
            p_recording_buffer = p_recording_buffer + 1
        
            # buffer grande circular a partir de mini-buffers: si se agota el ultimo mini-buffer volvemos a usar el primero
            if p_recording_buffer >= NUM_BUFFERS:
                p_recording_buffer = 0
            
            if num_buffers_recorded >= NUM_BUFFERS_WINDOW:                
                # producer thread
                #... generate item
                condition.acquire()
                #... add item to resource
                item = 1
                value = 1
   
                print "\n[PRODUCTOR][NUEVO BUFFER GRANDE]\n"
                p_processing_buffer = p_processing_buffer + 1
                
                if p_processing_buffer >= NUM_BUFFERS:
                    p_processing_buffer = 0
                
                # Copiamos los mini-buffers correspondientes en el buffer grande
                p_aux_item = 0
                for x in range(0, NUM_BUFFERS_WINDOW):
                    p_aux_buffer = p_processing_buffer+x
                    if p_aux_buffer >= NUM_BUFFERS:
                        p_aux_buffer = p_processing_buffer+x-NUM_BUFFERS
                    
                    AccXarray[p_aux_item:p_aux_item+MAX_ITEMS_BUFFER] = AccX_bufferArray[p_aux_buffer, :]
                    AccYarray[p_aux_item:p_aux_item+MAX_ITEMS_BUFFER] = AccY_bufferArray[p_aux_buffer, :]
                    AccZarray[p_aux_item:p_aux_item+MAX_ITEMS_BUFFER] = AccZ_bufferArray[p_aux_buffer, :]

                    p_aux_item = p_aux_item+MAX_ITEMS_BUFFER
                
                condition.notify() # signal that a new item is available
                condition.release()
    finally:
        count_lock.release() # release lock, no matter what

def main():
    global stop
    global AccX_bufferArray
    global AccY_bufferArray
    global AccZ_bufferArray
    global AccXarray
    global AccYarray
    global AccZarray    
    global p_recording_buffer
    global p_item_in_recording_buffer
    global count
    global item
    global num_buffers_recorded
    global num_items_recorded
    global p_processing_buffer
    
    # call print_so every second, 5 times total
    #do_every (1, print_so, 5)
    #demoArray = np.array([[1, 2, 3],[4,5,6],[7,8,9]], dtype=float)
    
    stop_lock.acquire()
    try:
        stop = 0 # access shared resource
    finally:
        stop_lock.release() # release lock, no matter what
    
    count_lock.acquire()
    try:
        count = 0 # access shared resource
    finally:
        count_lock.release() # release lock, no matter what
        
    item = 0
    # call print_hw two times per second, forever
    do_every (0.02, ReadAccelerometer)
    #do_every (1, ReadAccelerometer)
            
    while(1):
        # consumer thread
        condition.acquire()
        while True:
            #... get item from resource
            count_lock.acquire()
            try:
                if item:
                    print "CONSUMIDOR: NUEVO VALOR"
                    #print "ESTADO ARRAYS"
                    #print AccX_bufferArray
                    print "GRANDE"
                    print AccXarray
                    item = 0
                    #exit(1)
                    #print AccY_bufferArray
                    #print AccZ_bufferArray
                    break
            finally:
                count_lock.release() # release lock, no matter what
                
            condition.wait() # sleep until item becomes available
        condition.release()
        #... process item
        value = 0

#    while(1):
#        time.sleep(1)
#        print "."

if __name__ == "__main__":
    try:
        #jvm.start()
        main()
    except Exception, e:
        print(traceback.format_exc())
    finally:
        #jvm.stop()
        print("\nnum_buffers_recorded = " + str(num_buffers_recorded) + "\nnum_items_recorded = " + str(num_items_recorded) + "\n")
        stop_lock.acquire()
        try:
            stop = 1 # access shared resource
        finally:
            stop_lock.release() # release lock, no matter what
        
        #timer.cancel()
        #timer.join() 
        exit(1)
