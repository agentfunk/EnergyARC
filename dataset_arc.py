# %% Dataset
from __future__ import print_function, division

import numpy as np
import json
import matplotlib.pyplot as plt

training_data_path = "/data/code/ARC-AGI/data/"
import os
import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, utils


class ARCDataset(Dataset):
    """ARC Torch dataset."""

    def __init__(self, root_dir, mode="training", transform=None, no_of_demos=12):
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
        if mode == "training":
            self.tasks = self.__load_split(self.root_dir + "training")
        if mode == "evaluation":
            self.tasks = self.__load_split(self.root_dir + "evaluation")
        if mode == "both":
            tasks_training = self.__load_split(self.root_dir + "training")
            tasks_evaluation = self.__load_split(self.root_dir + "evaluation")
            self.tasks = (
                tasks_evaluation[0] + tasks_training[0],
                tasks_evaluation[1] + tasks_training[1],
            )

        self.transform = transform
        ## Preprocess
        # for i, task in enumerate(self.tasks):
        #     self.tasks[i] = self.transform(task)

        self.inputs = self.tasks[0][:64]  # ! process only two batches
        self.outputs = self.tasks[1][:64]

        for i, task in enumerate(self.inputs):
            self.inputs[i] = self.transform(task)
        for i, task in enumerate(self.outputs):
            self.outputs[i] = self.transform(task)

        self.inputs = [torch.stack(demos) for demos in self.inputs]
        self.inputs = torch.stack(self.inputs)
        self.outputs = [torch.stack(demos) for demos in self.outputs]
        self.outputs = torch.stack(self.outputs)

    def __len__(self):
        return len(self.inputs)

    def __getitem__(self, idx):
        sample = (self.inputs[idx], self.outputs[idx])
        return sample

    def __load_split(self, split_dir):
        tasks = []
        tasks_json = os.listdir(split_dir)
        for task_file in tasks_json:
            with open(os.path.join(split_dir, task_file)) as f:
                data = json.load(f)
                tasks.append(data)
        return self.__break_split(tasks)

    def __break_split(self, tasks):

        inputs = []
        outputs = []
        for item in tasks:
            demo_inputs = []
            demo_outputs = []
            for tasks_item in item["train"]:

                demo_inputs.append([ti for ti in tasks_item["input"]])
                demo_outputs.append([ti for ti in tasks_item["output"]])

            test_inputs = []
            test_outputs = []
            for tasks_item in item["test"]:
                test_inputs.append([ti for ti in tasks_item["input"]])
                test_outputs.append([ti for ti in tasks_item["output"]])

            # demo_inputs are [input_no, h, w]
            inputs.append(demo_inputs + test_inputs)
            # inputs is [task_no, input_no, h, w]
            outputs.append(demo_outputs + test_outputs)

        return (inputs, outputs)


# %%
class Preprocess(object):
    """Converts task inputs and outputs to tensors, but leaves the outer list structure"""

    def __call__(self, sample):
        inputs = sample

        for i, inp in enumerate(inputs):
            inputs[i] = torch.tensor(inp, dtype=torch.float32)  ## convert to Tensor
            # inputs[i] = inputs[i]/10.  # normalize
            inputs[i] = inputs[i].unsqueeze(0)  #  channels dim

        return inputs


class Padded_with_mask(object):
    """Pads all inputs and outputs to a 30x30 but adds another channel with a mask"""

    def __call__(self, sample, pad=30):

        inputs = sample
        for i, inp in enumerate(inputs):
            canvas = torch.ones([1, pad, pad]) * 10.0
            # pad_mask = torch.zeros([ 1, pad, pad])
            canvas[0, : inp.shape[1], : inp.shape[2]] = inp
            # pad_mask[ 0, :inp.shape[1], :inp.shape[2]] = torch.ones_like(inp)
            # canvas = map(convert_to_rgb, canvas.view([-1])).view([3, pad,pad])
            canvas = list(map(convert_to_rgb, torch.unbind(canvas.view([-1]))))
            canvas = torch.stack(canvas)
            inputs[i] = canvas.view([pad, pad, 3]).permute([2, 0, 1])

        return inputs


class Padded_no_of_demos(object):
    """Pads tasks with demo pairs duplicates"""

    def __init__(self, no_of_demos):
        self.no_of_demos = no_of_demos
        super(self.__class__, self).__init__()

    def __call__(self, sample):
        inputs = sample
        no_of_demos = self.no_of_demos
        li = len(inputs)

        # padd up to no_of_demos
        if li < no_of_demos:
            for it in range(no_of_demos - li):
                inputs.append(inputs[it])
                # inputs.append(torch.zeros(size=[2, 30, 30]))

        # limit anything above no_of_demos
        inputs = inputs[:no_of_demos]

        # Transforms from tuplie of lists to list of tuples. Each input output demo example is a tuple.
        return inputs
        # return ([(i, o) for i, o in zip(inputs, outputs)])


# preprocess = Preprocess()
# pad_with_mask= Padded_with_mask(30)
all_transforms = transforms.Compose(
    [Preprocess(), Padded_with_mask(), Padded_no_of_demos(6)]
)


# arc = ARCDataset('./ARC/data/', 'both', transform=all_transforms)
# aa = arc[3]


# %%

# transoforms the 10 integer values into a 3 dim embedding
colors = {
    0: [0.0, 0.0, 0.0],  # black
    1: [0.0, 0.0, 1.0],  # blue
    2: [1.0, 0.0, 0.0],  # red
    3: [0.0, 1.0, 0.0],  # green
    4: [1.0, 1.0, 0.0],  # yellow
    5: [0.7, 0.6, 0.5],  # ?grey
    6: [1.0, 0.0, 1.0],  # magenta
    7: [0.5, 0.5, 0.1],  # ?orange?
    8: [0.0, 1.0, 1.0],  # cyan
    9: [0.5, 0.1, 0.1],  # ?maroon
    10: [1.0, 1.0, 1.0],  # mask
}


def convert_to_rgb(c):
    return torch.tensor(
        colors[c.item()]
    )  # add item() to get the data from a zero dim tensor.


# %%
def show_task(inputs, outputs, channels_first=True):
    """displays an ARC task, provided as a list of inputs and outputs"""
    fig = plt.figure(figsize=[16, 34], facecolor=(0, 0, 0))
    no_of_demos = inputs.shape[0]
    for i, (inp, out) in enumerate(zip(inputs, outputs)):
        subplot = plt.subplot(no_of_demos + 1, 2, 2 * i + 1)
        channels = np.argmin(inp.shape)
        if channels_first:
            inp = inp.permute([1, 2, 0])
            out = out.permute([1, 2, 0])
        plt.imshow(inp)
        plt.title("demo " + str(i) + " q", color="w")
        plt.axis("off")
        subplot = plt.subplot(no_of_demos + 1, 2, 2 * i + 2)
        plt.imshow(out)
        plt.title("demo " + str(i) + " ans", color="w")
        plt.axis("off")
    return fig


d = ARCDataset(training_data_path, transform=all_transforms)
show_task(*d[0]).savefig("plot.png")
