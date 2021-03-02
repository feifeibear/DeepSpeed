'''
Copyright 2020 The Microsoft DeepSpeed Team
'''

import torch.nn.init as init
import torch
import torch.distributed as dist

# import for sanity testing only
#from .basic_moe import BasicMoE
from deepspeed.utils import logger, log_dist

import deepspeed.utils.groups as groups
from .sharded_moe import MOELayer, TopKGate
from .experts import Experts
import copy 

class MoE(torch.nn.Module):
    '''
        DeepSpeed MOE API: This defines a simple API that can be used from client-side code.
        E.g. See more details of usage from Megatron-LM code in https://github.com/microsoft/DeepSpeedExamples/tree/amawa/moe
    '''
    def __init__(self, hidden_size, output_dropout_prob, expert, num_experts = 1, k = 1, capacity_factor = 1.,
                 noisy_gate = False): 
        super(MoE, self).__init__()

        assert groups.is_initialized(), \
            'Please call deepspeed.utils.groups.initialize() before using MoE layers'

        num_local_experts = num_experts // groups.get_expert_parallel_world_size()
        
        log_dist(f'num_experts: {num_experts} | num_local_experts: {num_local_experts} | expert_parallel_size: {groups.get_expert_parallel_world_size()}', [0])

        self.num_experts = num_experts
        experts = Experts(expert, num_local_experts)
        # TODO Capacity factor needs to be configurable
        # TODO add top-k gate
        self.deepspeed_moe = MOELayer(TopKGate(hidden_size, num_experts, k, capacity_factor, noisy_gate), 
                                      experts,
                                      num_local_experts,
                                      group=groups.get_expert_parallel_group())

        self.dropout = torch.nn.Dropout(output_dropout_prob)

    def forward(self, hidden_states):
        output = self.deepspeed_moe(hidden_states)
        output = self.dropout(output)
        return output, self.deepspeed_moe.l_aux
