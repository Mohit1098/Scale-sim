import math
from tqdm import tqdm

# Assumptions: 
# No. of columns of PE array is a multiple of (H-R+1)/strides to avoid folding
# num_blocks = dim_cols / ((H-R+1)/strides)
# Partial sums from different channels are added while storing in SRAM (instead of just store)
# No. of rows of PE array is W
# PEs are assumed to have enough memory to hold ifmap row
# strides should no matter here (since striding can be simply managed by moving the input map appropriately)
# Filters are stored in M * C * R * S format
# Inputs in C * H * W format
# Outputs in M * ofmap_h * ofmap_w

def sram_traffic(dimension_rows = 3, dimension_cols = 3,
               ifmap_h = 5, ifmap_w = 5, filt_h = 3, filt_w = 3, num_channels = 1, strides = 1, num_filt = 1, 
               ofmap_base=2000000, filt_base=1000000, ifmap_base=0, 
               sram_read_trace_file="sram_read.csv", sram_write_trace_file="sram_write.csv"
              ):
    cycle = 0
    ofmap_h = (ifmap_h - filt_h + strides) // strides
    num_blocks = dimension_cols
    read_cycles, util = gen_read_trace(cycle, ifmap_h, ifmap_w, filt_h, filt_w, num_channels, num_filt,
                                       num_blocks, strides, ofmap_base, filt_base, ifmap_base, sram_read_trace_file)
    
    write_cycles = gen_write_trace(cycle, ifmap_h, ifmap_w, filt_h, filt_w, num_channels, num_filt,
                                   num_blocks, strides, ofmap_base, filt_base, ifmap_base, sram_write_trace_file)
    
    str_cycles = str(max(read_cycles, write_cycles))
    return (str_cycles, util)
    
    

def gen_read_trace(cycle = 0, ifmap_h = 5, ifmap_w = 5, filt_h = 3, filt_w = 3, 
                   num_channels = 1, num_filt = 1, num_blocks = 2, strides = 1,
                   ofmap_base=2000000, filt_base=1000000, ifmap_base=0,
                   sram_read_trace_file="sram_read.csv"):
    
    dim_rows = filt_h
    dim_diag = ifmap_h
    dim_cols = (ifmap_h - filt_h + strides) // strides

    outfile = open(sram_read_trace_file, 'w')

    
    # Total number of PE cycles
    local_cycle = 0 
    tot_conv = num_channels * num_filt
    pbar = tqdm(total = tot_conv)
    cur_conv = 0
    r2 = filt_h * filt_w
    r2c = r2 * num_channels
    h2 = ifmap_h * ifmap_w
    
    working_blocks = 0
    is_working_block = []
    
    # Dimension: num_blocks * dim_rows -> sends filters across
    row_base_addr = [] 
    
    # Dimension: num_blocks * ifmap_h -> sends input maps across 
    diag_base_addr = []
    
    for b in range(num_blocks):
        
        if(cur_conv >= tot_conv):
            is_working_block.append(False)
            continue
            
        cur_filt = cur_conv // num_channels
        cur_channel = cur_conv % num_channels
        
        row_base_addr_per_block = []
        diag_base_addr_per_block = []
        
        for r in range(dim_rows):
            row_base_addr_per_block.append(filt_base + cur_filt * r2c + cur_channel * r2 + r * filt_w)
            
        for d in range(dim_diag):
            diag_base_addr_per_block.append(ifmap_base + cur_channel * h2 + d * ifmap_w)
        
        cur_conv += 1
        is_working_block.append(True)
        working_blocks += 1
        
        row_base_addr.append(row_base_addr_per_block)
        diag_base_addr.append(diag_base_addr_per_block)
        
    cycle_factor = 1 # Each PE takes cycle_factor cycles for one input row
    
    clk = -1
    
    while working_blocks > 0:
        ifmap_read = ""
        filter_read = ""
        clk += 1
        
        for b in range(num_blocks):
            
            if not is_working_block[b]:
                continue
                
            cur_iter = clk % dim_cols
            
            filt_row_idx = dim_rows - 1 - cur_iter
            if(filt_row_idx >= 0): 
                for c in range(filt_w):
                    filter_read += str(row_base_addr[b][filt_row_idx] + c) + ", "
                
            ifmap_row_idx = dim_rows - 1 - cur_iter
            if(ifmap_row_idx >= 0 and ifmap_row_idx < ifmap_h): 
                for c in range(ifmap_w):
                    ifmap_read += str(diag_base_addr[b][ifmap_row_idx] + c) + ", "

            ifmap_row_idx = dim_rows - 1 + cur_iter
            if(cur_iter !=0 and ifmap_row_idx >= 0 and ifmap_row_idx < ifmap_h): 
                for c in range(ifmap_w):
                    ifmap_read += str(diag_base_addr[b][ifmap_row_idx] + c) + ", "
              
            cur_iter = clk % dim_cols
            
            if not (clk > 0 and cur_iter == dim_cols - 1):
                continue
                
            pbar.update(1)    
            
            # Add next conv window (similar to initialisation)
            if(cur_conv >= tot_conv):
                is_working_block[b] = False
                working_blocks -= 1
                continue
            
            cur_filt = cur_conv // num_channels
            cur_channel = cur_conv % num_channels

            row_base_addr_per_block = []
            diag_base_addr_per_block = []

            for r in range(dim_rows):
                row_base_addr_per_block.append(filt_base + cur_filt * r2c + cur_channel * r2 + r * filt_w)

            for d in range(dim_diag):
                diag_base_addr_per_block.append(ifmap_base + cur_channel * h2 + d * ifmap_w)

            cur_conv += 1
            
            row_base_addr[b] = row_base_addr_per_block
            diag_base_addr[b] = diag_base_addr_per_block
            
        global_cycle = cycle + local_cycle
        entry = str(global_cycle) +", " + ifmap_read + filter_read + "\n"
        outfile.write(entry)
        local_cycle += cycle_factor
        
    pbar.close()
    outfile.close()
    
    util_perc = (1 / (local_cycle / cycle_factor)) * 100
    return (local_cycle + cycle, util_perc)

def gen_write_trace(cycle = 0, ifmap_h = 5, ifmap_w = 5, filt_h = 3, filt_w = 3, 
                    num_channels = 1, num_filt = 1, num_blocks = 1, strides = 1,
                    fmap_base=2000000, filt_base=1000000, ifmap_base=0,
                    sram_write_trace_file = "sram_write.csv"
                   ):
    dim_rows = filt_h
    dim_cols = (ifmap_h - filt_h + strides) // strides
    
    ofmap_h = dim_cols
    ofmap_w = (ifmap_w - filt_w + strides) // strides
    r2 = ofmap_h * ofmap_w
    
    outfile = open(sram_write_trace_file, 'w')

    local_cycle = 0 
    tot_conv = num_channels * num_filt
    cur_conv = 0
    pbar = tqdm(total = tot_conv)
    
    working_blocks = 0
    is_working_block = []
    
    col_base_addr = []
    
    for b in range(num_blocks):
        if cur_conv >= tot_conv:
            is_working_block.append(False)
            continue
        
        col_base_addr_per_block = []
        
        for c in range(dim_cols):
            col_base_addr_per_block.append(fmap_base + cur_conv * r2 + c * ofmap_w)
            
        cur_conv += 1
        col_base_addr.append(col_base_addr_per_block)
        is_working_block.append(True)
        working_blocks += 1
        
    cycle_factor = 1 # Each PE takes cycle_factor cycles for one input row
    clk = - dim_rows - 1

    while working_blocks > 0:
        ofmap_write = ""
        clk += 1
        
        for b in range(num_blocks):
            if not is_working_block[b]:
                continue
            
            cur_iter = clk % dim_cols
            
            if clk >= 0:
                for w in range(ofmap_w):
                    ofmap_write += str(col_base_addr[b][cur_iter] + w) + ", "

            if not (clk > 0 and cur_iter == dim_cols - 1):
                continue
            
            pbar.update(1)
            
            if(cur_conv >= tot_conv):
                is_working_block[b] = False
                working_blocks -= 1
                
            # Adding next output window
            col_base_addr_per_block = []

            for c in range(dim_cols):
                col_base_addr_per_block.append(fmap_base + cur_conv * r2 + c * ofmap_w)

            cur_conv += 1
            col_base_addr[b] = col_base_addr_per_block
            
        global_cycle = cycle + local_cycle
        
        entry = str(global_cycle) +", " + ofmap_write + "\n"
        outfile.write(entry)
        
        local_cycle += cycle_factor
        
    pbar.close()
    outfile.close()
    
    return (cycle + local_cycle)

if __name__ == '__main__':
    cycles, util = rs_traffic()
    print("Cycles: {}, Utilization: {}".format(cycles, util))