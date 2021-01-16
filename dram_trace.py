import os.path
import math
from tqdm import tqdm
from collections import defaultdict
import copy


def prune(input_list):
    l = []

    for e in input_list:
        e = e.strip()
        if e != '' and e != ' ':
            l.append(e)

    return l




# Assumption :
#              Sram to SysArray and vice versa is very fast
#              Compute cycles and memory cycles have same frequency (this was already assumed in original implementation)

def dram_traces_with_delay(
    filter_sram_size = 64, ifmap_sram_size= 64, ofmap_sram_size = 64,
    filt_base = 1000000, ifmap_base=0, ofmap_base = 2000000,

    word_size_bytes = 1,
    default_read_bw = 10,
    default_write_bw = 10,

    buffer_swap_factor=0.7,

    sram_read_trace_file = "sram_read.csv",
    sram_write_trace_file = "sram_write.csv",
    dram_filter_trace_file = "dram_filter_read.csv",
    dram_ifmap_trace_file = "dram_ifmap_read.csv",
    dram_ofmap_trace_file = "dram_ofmap_write.csv"
    ):



    sram_read_requests=open(sram_read_trace_file,'r')
    sram_write_requests=open(sram_write_trace_file,'r')


    dict_sram_ifmap_requests={}
    dict_sram_ofmap_requests={}
    dict_sram_filter_requests={}


    dict_sram_read_requests_max_key=0
    dict_sram_write_requests_max_key=0

    for entry in sram_read_requests:
        elems = entry.strip().split(',')
        elems = prune(elems)
        elems = [float(x) for x in elems]
        dict_sram_ifmap_requests[int(elems[0])]=[e for e in elems[1:] if e<filt_base]
        dict_sram_filter_requests[int(elems[0])]=[e for e in elems[1:] if e>=filt_base]
        dict_sram_read_requests_max_key=int(elems[0])
    sram_read_requests.close()

    for entry in sram_write_requests:
        elems = entry.strip().split(',')
        elems = prune(elems)
        elems = [float(x) for x in elems]
        dict_sram_ofmap_requests[int(elems[0])]=[e for e in elems[1:]]
        dict_sram_write_requests_max_key=int(elems[0])
    sram_write_requests.close()

    max_compute_cycle = max(dict_sram_write_requests_max_key,dict_sram_read_requests_max_key)



    dram_filter_trace_requests = open(dram_filter_trace_file,'w')
    dram_ifmap_trace_requests  = open(dram_ifmap_trace_file,'w')
    dram_ofmap_trace_requests  = open(dram_ofmap_trace_file,'w')

    cycle=0
    compute_cycle=0

    dict_sram_ifmap_requests2=copy.deepcopy(dict_sram_ifmap_requests)
    dict_sram_ofmap_requests2=copy.deepcopy(dict_sram_ofmap_requests)
    dict_sram_filter_requests2=copy.deepcopy(dict_sram_filter_requests)


    # cycle pointers in original SRAM files
    sram_ofmap_buffer2_cycle=0
    sram_ifmap_buffer2_cycle=0
    sram_filter_buffer2_cycle=0


    #Simulating Double Buffer
    sram_ofmap_buffer1_size=0
    sram_ifmap_buffer1=set()
    sram_filter_buffer1=set()

    sram_ofmap_buffer2_size=0
    sram_ifmap_buffer2=set()
    sram_filter_buffer2=set()

    # Iterating cycles
    while(True):

        # Work is finished
        if(compute_cycle>max_compute_cycle and sram_ofmap_buffer1_size==0 and sram_ofmap_buffer2_size==0):
            break

        # fill ifmap in one cycle
        if(len(sram_ifmap_buffer2)<ifmap_sram_size and sram_ifmap_buffer2_cycle<=max_compute_cycle):

            #Bandwidth
            count = math.floor(default_read_bw/word_size_bytes)
            trace= str(cycle)+", "

            while(len(sram_ifmap_buffer2)<ifmap_sram_size
                    and count>0
                    and sram_ifmap_buffer2_cycle<=max_compute_cycle):

                while(((sram_ifmap_buffer2_cycle not in dict_sram_ifmap_requests) or len(dict_sram_ifmap_requests[sram_ifmap_buffer2_cycle])==0)
                        and sram_ifmap_buffer2_cycle<=max_compute_cycle):
                    sram_ifmap_buffer2_cycle+=1

                # Only if element not already present in buffer
                if(sram_ifmap_buffer2_cycle<=max_compute_cycle):
                    if(dict_sram_ifmap_requests[sram_ifmap_buffer2_cycle][0] not in sram_ifmap_buffer2):
                        sram_ifmap_buffer2.add(dict_sram_ifmap_requests[sram_ifmap_buffer2_cycle][0])
                        trace+=str(dict_sram_ifmap_requests[sram_ifmap_buffer2_cycle][0])+", "
                        count-=1

                    dict_sram_ifmap_requests[sram_ifmap_buffer2_cycle].pop(0)

            trace+="\n"

            dram_ifmap_trace_requests.write(trace)


        # fill filter in one cycle
        if(len(sram_filter_buffer2)<filter_sram_size and sram_filter_buffer2_cycle<=max_compute_cycle):

            count = math.floor(default_read_bw/word_size_bytes)
            trace= str(cycle)+", "

            while(len(sram_filter_buffer2)<filter_sram_size and count>0 and sram_filter_buffer2_cycle<=max_compute_cycle):

                while(((sram_filter_buffer2_cycle not in dict_sram_filter_requests) or len(dict_sram_filter_requests[sram_filter_buffer2_cycle])==0) and sram_filter_buffer2_cycle<=max_compute_cycle):
                    sram_filter_buffer2_cycle+=1

                if(sram_filter_buffer2_cycle<=max_compute_cycle):

                    if(dict_sram_filter_requests[sram_filter_buffer2_cycle][0] not in sram_filter_buffer2):
                        sram_filter_buffer2.add(dict_sram_filter_requests[sram_filter_buffer2_cycle][0])
                        trace+=str(dict_sram_filter_requests[sram_filter_buffer2_cycle][0])+", "
                        count-=1

                    dict_sram_filter_requests[sram_filter_buffer2_cycle].pop(0)

            trace+="\n"

            dram_filter_trace_requests.write(trace)



        # Move data from sram_ofmap_buffer2 to DRAM in one cycle
        if(sram_ofmap_buffer2_size>0):
            count = math.floor(default_write_bw/word_size_bytes)
            trace= str(cycle)+", "

            while(sram_ofmap_buffer2_size>0 and count>0):

                while((sram_ofmap_buffer2_cycle not in dict_sram_ofmap_requests) or len(dict_sram_ofmap_requests[sram_ofmap_buffer2_cycle])==0):
                    sram_ofmap_buffer2_cycle+=1

                sram_ofmap_buffer2_size-=1
                trace+=str(dict_sram_ofmap_requests[sram_ofmap_buffer2_cycle][0])+", "
                dict_sram_ofmap_requests[sram_ofmap_buffer2_cycle].pop(0)

                count-=1

            trace+="\n"
            dram_ofmap_trace_requests.write(trace)

        #After Draining write buffer check if it requires swap
        if(sram_ofmap_buffer2_size==0):
            sram_ofmap_buffer2_size=sram_ofmap_buffer1_size
            sram_ofmap_buffer1_size=0


        #check for all ifmap data that can be taken in from sram into array
        if((compute_cycle in dict_sram_ifmap_requests2) and len(dict_sram_ifmap_requests2[compute_cycle])>0):

            if((dict_sram_ifmap_requests2[compute_cycle][0] not in sram_ifmap_buffer1)
                    # Buffer swaping policy
                    and (sram_ifmap_buffer2_cycle>max_compute_cycle or len(sram_ifmap_buffer2)>buffer_swap_factor*ifmap_sram_size)):
                sram_ifmap_buffer1=sram_ifmap_buffer2
                sram_ifmap_buffer2=set()

            while(len(dict_sram_ifmap_requests2[compute_cycle])>0 and (dict_sram_ifmap_requests2[compute_cycle][0] in sram_ifmap_buffer1)):
                dict_sram_ifmap_requests2[compute_cycle].pop(0)


        #check for all filter data that can be taken in from sram into array
        if((compute_cycle in dict_sram_filter_requests2) and len(dict_sram_filter_requests2[compute_cycle])>0):

            if(dict_sram_filter_requests2[compute_cycle][0] not in sram_filter_buffer1
                and (sram_filter_buffer2_cycle>max_compute_cycle or len(sram_filter_buffer2)>buffer_swap_factor*filter_sram_size)):
                sram_filter_buffer1=sram_filter_buffer2
                sram_filter_buffer2=set()

            while(len(dict_sram_filter_requests2[compute_cycle])>0 and (dict_sram_filter_requests2[compute_cycle][0] in sram_filter_buffer1)):
                dict_sram_filter_requests2[compute_cycle].pop(0)



        #write ofmap data from array to sram
        if((compute_cycle in dict_sram_ofmap_requests2) and (len(dict_sram_ofmap_requests2[compute_cycle])>0)):
            # print(compute_cycle,len(dict_sram_ofmap_requests2[compute_cycle]))
            if(sram_ofmap_buffer1_size<ofmap_sram_size ):

                while(len(dict_sram_ofmap_requests2[compute_cycle])>0 and sram_ofmap_buffer1_size<ofmap_sram_size):
                    sram_ofmap_buffer1_size+=1
                    dict_sram_ofmap_requests2[compute_cycle].pop(0)

        cycle+=1

        # If the whole calculation required for original compute cycle is done
        if((compute_cycle not in dict_sram_ifmap_requests2 or len(dict_sram_ifmap_requests2[compute_cycle])==0)
            and (compute_cycle not in dict_sram_ofmap_requests2 or len(dict_sram_ofmap_requests2[compute_cycle])==0)
            and (compute_cycle not in dict_sram_filter_requests2 or len(dict_sram_filter_requests2[compute_cycle])==0)
            ):
            compute_cycle+=1

    dram_filter_trace_requests.close()
    dram_ifmap_trace_requests.close()
    dram_ofmap_trace_requests.close()

    return cycle


def dram_trace_read_v2(
        sram_sz         = 512 * 1024,
        word_sz_bytes   = 1,
        min_addr = 0, max_addr=1000000,
        default_read_bw = 10,               # this is arbitrary
        sram_trace_file = "sram_log.csv",
        dram_trace_file = "dram_log.csv"
    ):

    t_fill_start    = -1
    t_drain_start   = 0
    init_bw         = default_read_bw         # Taking an arbitrary initial bw of 4 bytes per cycle

    sram = set()

    sram_requests = open(sram_trace_file, 'r')
    dram          = open(dram_trace_file, 'w')

    #for entry in tqdm(sram_requests):
    for entry in sram_requests:
        elems = entry.strip().split(',')
        elems = prune(elems)
        elems = [float(x) for x in elems]

        clk = elems[0]

        for e in range(1, len(elems)):

            if (elems[e] not in sram) and (elems[e] >= min_addr) and (elems[e] < max_addr):

                # Used up all the unique data in the SRAM?
                if len(sram) + word_sz_bytes > sram_sz:

                    if t_fill_start == -1:
                        t_fill_start = t_drain_start - math.ceil(len(sram) / (init_bw * word_sz_bytes))

                    # Generate the filling trace from time t_fill_start to t_drain_start
                    cycles_needed   = t_drain_start - t_fill_start
                    words_per_cycle = math.ceil(len(sram) / (cycles_needed * word_sz_bytes))

                    c = t_fill_start

                    while len(sram) > 0:
                        trace = str(c) + ", "

                        for _ in range(words_per_cycle):
                            if len(sram) > 0:
                                p = sram.pop()
                                trace += str(p) + ", "

                        trace += "\n"
                        dram.write(trace)
                        c += 1

                    t_fill_start    = t_drain_start
                    t_drain_start   = clk

                # Add the new element to sram
                sram.add(elems[e])


    if len(sram) > 0:
        if t_fill_start == -1:
            t_fill_start = t_drain_start - math.ceil(len(sram) / (init_bw * word_sz_bytes))

        # Generate the filling trace from time t_fill_start to t_drain_start
        cycles_needed = t_drain_start - t_fill_start
        words_per_cycle = math.ceil(len(sram) / (cycles_needed * word_sz_bytes))

        c = t_fill_start

        while len(sram) > 0:
            trace = str(c) + ", "

            for _ in range(words_per_cycle):
                if len(sram) > 0:
                    p = sram.pop()
                    trace += str(p) + ", "

            trace += "\n"
            dram.write(trace)
            c += 1

    sram_requests.close()
    dram.close()


def dram_trace_write(ofmap_sram_size = 64,
                     data_width_bytes = 1,
                     default_write_bw = 10,                     # this is arbitrary
                     sram_write_trace_file = "sram_write.csv",
                     dram_write_trace_file = "dram_write.csv"):

    traffic = open(sram_write_trace_file, 'r')
    trace_file  = open(dram_write_trace_file, 'w')

    last_clk = 0
    clk = 0

    sram_buffer = [set(), set()]
    filling_buf     = 0
    draining_buf    = 1

    for row in traffic:
        elems = row.strip().split(',')
        elems = prune(elems)
        elems = [float(x) for x in elems]

        clk = elems[0]

        # If enough space is in the filling buffer
        # Keep filling the buffer
        if (len(sram_buffer[filling_buf]) + (len(elems) - 1) * data_width_bytes ) < ofmap_sram_size:
            for i in range(1,len(elems)):
                sram_buffer[filling_buf].add(elems[i])

        # Filling buffer is full, spill the data to the other buffer
        else:
            # If there is data in the draining buffer
            # drain it
            #print("Draining data. CLK = " + str(clk))
            if len(sram_buffer[draining_buf]) > 0:
                delta_clks = clk - last_clk
                data_per_clk = math.ceil(len(sram_buffer[draining_buf]) / delta_clks)
                #print("Data per clk = " + str(data_per_clk))

                # Drain the data
                c = last_clk + 1
                while len(sram_buffer[draining_buf]) > 0:
                    trace = str(c) + ", "
                    c += 1
                    for _ in range(int(data_per_clk)):
                        if len(sram_buffer[draining_buf]) > 0:
                            addr = sram_buffer[draining_buf].pop()
                            trace += str(addr) + ", "

                    trace_file.write(trace + "\n")

            #Swap the ids for drain buffer and fill buffer
            tmp             = draining_buf
            draining_buf    = filling_buf
            filling_buf     = tmp

            #Set the last clk value
            last_clk = clk

            #Fill the new data now
            for i in range(1,len(elems)):
                sram_buffer[filling_buf].add(elems[i])

    #Drain the last fill buffer
    reasonable_clk = clk
    if len(sram_buffer[draining_buf]) > 0:
        #delta_clks = clk - last_clk
        #data_per_clk = math.ceil(len(sram_buffer[draining_buf]) / delta_clks)
        data_per_clk = default_write_bw
        #print("Data per clk = " + str(data_per_clk))

        # Drain the data
        c = last_clk + 1
        while len(sram_buffer[draining_buf]) > 0:
            trace = str(c) + ", "
            c += 1
            for _ in range(int(data_per_clk)):
                if len(sram_buffer[draining_buf]) > 0:
                    addr = sram_buffer[draining_buf].pop()
                    trace += str(addr) + ", "

            trace_file.write(trace + "\n")
            reasonable_clk = max(c, clk)

    if len(sram_buffer[filling_buf]) > 0:
        data_per_clk = default_write_bw

        # Drain the data
        c = reasonable_clk + 1
        while len(sram_buffer[filling_buf]) > 0:
            trace = str(c)+ ", "
            c += 1
            for _ in range(int(data_per_clk)):
                if len(sram_buffer[filling_buf]) > 0:
                    addr = sram_buffer[filling_buf].pop()
                    trace += str(addr) + ", "

            trace_file.write(trace + "\n")


    #All traces done
    traffic.close()
    trace_file.close()

if __name__ == "__main__":
    dram_trace_read_v2(min_addr=0, max_addr=1000000, dram_trace_file="ifmaps_dram_read.csv")
    dram_trace_read_v2(min_addr=1000000, max_addr=100000000, dram_trace_file="filter_dram_read.csv")
        #dram_trace_read(filter_sram_sz=1024, ifmap_sram_sz=1024, sram_trace_file="sram_read.csv")
        #dram_trace_write(ofmap_sram_size=1024,sram_write_trace_file="yolo_tiny_layer1_write.csv", dram_write_trace_file="yolo_tiny_layer1_dram_write.csv")
