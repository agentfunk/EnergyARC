#%% Dataset
from __future__ import print_function, division

import numpy as np
import json
import matplotlib.pyplot as plt

training_data_path = './ARC/data/training'
import os

train = []
training_json = os.listdir(training_data_path)
for tj in training_json:
    with open(os.path.join(training_data_path,tj)) as f:
        data = json.load(f)
        train.append(data)
# %%
data['test'][0]['input']
# %%
# 
# plt.imshow(data['train'][0]['output'])

# %%
items = []
for item in train:
    for train_item in item['train']:
        items.append(train_item['input'])
        items.append(train_item['output'])
    for train_item in item['test']:
        items.append(train_item['input'])
        items.append(train_item['output'])

items = np.array(items)
#%
sizes_x = [(len(xx)) for xx in items]
sizes_y = [(len(xx[0])) for xx in items]
#%


# %%
sizes_x ==sizes_y

# %%

import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, utils

class ARCDataset(Dataset):
    """ARC Torch dataset."""

    def __init__(self,  root_dir, mode='training', transform=None, no_of_demos=12):
        """
        Args:
            root_dir (string): Directory with all the data.
            mode: 'training' to load training tasks
                  'evaluation' to load evalualtion tasks
               or 'both' to load all tasks available
            transform (callable, optional): Optional transform to be applied
                on a sample.
            no_of_demos: for efficiency task demo pairs will be made into batches. 
                This limit on the max no of demos per task improves efficiency and number of computations.
                but exludes tasks with high number of demos. 
        """
        self.root_dir = root_dir
        if mode == 'training':
            self.tasks = self.__load_split( self.root_dir + 'training')
        if mode == 'evaluation':
            self.tasks = self.__load_split( self.root_dir + 'evaluation')
        if mode == 'both':
            tasks_training   = self.__load_split(self.root_dir + 'training')
            tasks_evaluation = self.__load_split(self.root_dir + 'evaluation')
            self.tasks = (tasks_evaluation[0] + tasks_training[0], tasks_evaluation[1] + tasks_training[1])

        # Limit to tasks with a number of demos below cut off given by no_of_demos
        # convert tasks from a tuple of lists to a list of tuples
        tasks = []
        for i in range(len(self.tasks[0])):
            tasks.append((self.tasks[0][i],self.tasks[1][i]))
        self.tasks = tasks

        self.tasks = [task for task in self.tasks if len(task) <= no_of_demos]
        
        self.transform = transform
        

        ## Preprocess
        for i, task in enumerate(self.tasks):
            self.tasks[i] = self.transform(task)

        # self.inputs = self.tasks[0]
        # self.outputs = self.tasks[1]

    def __len__(self):
        return len(self.tasks)

    def __load_split(self, split_dir):
        tasks = []
        tasks_json = os.listdir(split_dir)
        for task_file in tasks_json:
            with open(os.path.join(split_dir,task_file)) as f:
                data = json.load(f)
                tasks.append(data)
        return self.__break_split(tasks)

    def __break_split(self, tasks):
        
        inputs = []
        outputs = []
        for item in tasks:
            demo_inputs = []
            demo_outputs = []
            for tasks_item in item['train']:

                demo_inputs.append( [ti for ti in tasks_item['input']] )
                demo_outputs.append( [ti for ti in tasks_item['output']] )

            test_inputs=[]
            test_outputs=[]
            for tasks_item in item['test']:
                test_inputs.append([ti for ti in tasks_item['input']] )
                test_outputs.append([ti for ti in tasks_item['output']])
            
            #demo_inputs are [input_no, h, w]
            inputs.append (demo_inputs + test_inputs )
            #inputs is [task_no, input_no, h, w]
            outputs.append(demo_outputs+ test_outputs)
            
        return (inputs,outputs)

    def __getitem__(self, idx):
        # if torch.is_tensor(idx):
        #     idx = idx.tolist()

        sample = self.tasks[idx]
        
        # if self.transform:
            # sample = self.transform(sample)

        return sample

# %%
class Preprocess(object):
    """ Converts task inputs and outputs to tensors, but leaves the outer list structure"""

    def __call__(self, sample, device='cuda'):
        inputs, outputs = sample[0], sample[1]

        # for t task in enumerate(inputs):
        for i, inp in enumerate(inputs):
            inputs[i] = torch.tensor(inp, dtype=torch.float32) ## convert to Tensor
            inputs[i] = inputs[i]/10.  # normalize
            inputs[i] = inputs[i].unsqueeze(0) #  channels dim
                

        # for t task in enumerate(outputs):
        for i, inp in enumerate(outputs):
            outputs[i] = torch.tensor(inp, dtype=torch.float32) ## convert to Tensor
            outputs[i] = outputs[i]/10.  # normalize
            outputs[i] = outputs[i].unsqueeze(0) # addand channels dim
        return (inputs, outputs)

class Padded_with_mask(object):
    """ Pads all inputs and outputs to a 30x30 but adds another channel with a mask"""

    def __call__(self, sample, pad=30, device='cuda'):
        inputs, outputs = sample[0], sample[1]

        # for t task in enumerate(inputs):
        for i, inp in enumerate(inputs):
            canvas = torch.zeros([ 1, pad, pad])
            pad_mask = torch.zeros([ 1, pad, pad])
            canvas[ 0, :inp.shape[1], :inp.shape[2]] = inp 
            pad_mask[ 0, :inp.shape[1], :inp.shape[2]] = torch.ones_like(inp)
            inputs[i] = torch.cat([canvas, pad_mask], dim=0) #concat at the channel dim [batch, channel, h, w]

    # for t task in enumerate(outputs):
        for i, inp in enumerate(outputs):
            canvas = torch.zeros([1, pad, pad])
            pad_mask = torch.zeros([1, pad, pad])
            canvas[ 0, :inp.shape[1], :inp.shape[2]] = inp 
            pad_mask[ 0, :inp.shape[1], :inp.shape[2]] = torch.ones_like(inp)
            outputs[i] = torch.cat([canvas, pad_mask], dim=0) #concat at the channel dim [batch, channel, h, w]
        # ipdb.set_trace()
        return ([(i, o) for i, o in zip(inputs, outputs)])

class Padded_no_of_demos(object):
    """ Pads tasks with demo pairs made of zeros"""

    def __call__(self, sample, no_of_demos, device='cuda'):
        inputs, outputs = sample[0], sample[1]

        # for t task in enumerate(inputs):
        for i, inp in enumerate(inputs):
            canvas = torch.zeros([ 1, pad, pad])
            pad_mask = torch.zeros([ 1, pad, pad])
            canvas[ 0, :inp.shape[1], :inp.shape[2]] = inp 
            pad_mask[ 0, :inp.shape[1], :inp.shape[2]] = torch.ones_like(inp)
            inputs[i] = torch.cat([canvas, pad_mask], dim=0) #concat at the channel dim [batch, channel, h, w]

    # for t task in enumerate(outputs):
        for i, inp in enumerate(outputs):
            canvas = torch.zeros([1, pad, pad])
            pad_mask = torch.zeros([1, pad, pad])
            canvas[ 0, :inp.shape[1], :inp.shape[2]] = inp 
            pad_mask[ 0, :inp.shape[1], :inp.shape[2]] = torch.ones_like(inp)
            outputs[i] = torch.cat([canvas, pad_mask], dim=0) #concat at the channel dim [batch, channel, h, w]
        # ipdb.set_trace()
        return ([(i, o) for i, o in zip(inputs, outputs)])


# preprocess = Preprocess()
# pad_with_mask= Padded_with_mask(30)
all_transforms = transforms.Compose([Preprocess(), Padded_with_mask()])


# arc = ARCDataset('./ARC/data/', 'both', transform=all_transforms)
# aa = arc[3]



def sample_data(loader):
    loader_iter = iter(loader)

    while True:
        try:
            yield next(loader_iter)

        except StopIteration:
            loader_iter = iter(loader)
            yield next(loader_iter)


dataset = ARCDataset('./ARC/data/', 'both', transform= all_transforms) #, transform=transforms.Normalize(0., 10.)
loader = DataLoader(dataset, batch_size=1, shuffle=False, num_workers=1) # Error: Couldn't open shared event, when workers is 4, hmmm but also 1
# loader = tqdm(enumerate(sample_data(loader)))

# loader_iter = iter(loader)
# n = next(loader_iter)


# So now self.tasks has dims [task ID, 0 for inputs 1 for outputs, example ID, channels, height, width]
# it is a list of tuples. Each entry is a task. The tuple is its inputs and outputs, with the demo/test merged.
# dlist(self.tasks)
# 800
# 2
# 4
# 2
# 30
# 30
# but if using a DataLoader and iterater it appropriately adds a batch dim right before channels.
# dlist(n)
# 2
# 4
# 1
# 2
# 30
# 30
#But batching throgh the dataloader still does not work, it only knows tensors and will batch the first dim of tensor and ignore the list structure.