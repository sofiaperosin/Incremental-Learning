# -*- coding: utf-8 -*-
"""FINETUNING.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1qLYSKyTMeUXpD-uNVPwfJKHBFzgTjjHO

**MODULES**
"""

import torch
import torch.nn as nn
from torch.nn import BCEWithLogitsLoss
import torchvision.transforms as transforms
from torchvision.datasets import CIFAR10
from torchvision.datasets import CIFAR100
import torch.optim as optim


import numpy as np
from PIL import Image
from matplotlib import pyplot as plt
from sklearn.metrics import confusion_matrix

import random
import math

"""**ICIFAR100**"""

class iCIFAR10(CIFAR10):
  def __init__(self, root,classes,train,transform=None,target_transform=None,download=False):
    super(iCIFAR10, self).__init__(root,train=train,transform=transform,target_transform=target_transform,download=download)
    
    train_data = []
    train_labels = []

    for i in range(len(self.data)):
      if self.targets[i] in classes:
        train_data.append(self.data[i])
        train_labels.append(self.targets[i])

    self.data = np.array(train_data)
    self.targets = train_labels
  
  def __getitem__(self, index):
    img, target = self.data[index], self.targets[index]
    img = Image.fromarray(img)
    
    if self.transform is not None:
      img = self.transform(img)
    
    if self.target_transform is not None:
      target = self.target_transform(target)
    
    return index, img, target

  def __len__(self):
    return len(self.data)

  def get_image_class(self, label):
    return self.data[np.array(self.targets) == label]

  def append(self, images, labels):
    self.data = np.concatenate((self.data, images), axis=0)
    self.targets = self.targets + labels

class iCIFAR100(iCIFAR10):
    base_folder = 'cifar-100-python'
    url = "http://www.cs.toronto.edu/~kriz/cifar-100-python.tar.gz"
    filename = "cifar-100-python.tar.gz"
    tgz_md5 = 'eb9058c3a382ffc7106e4002c42a8d85'
    train_list = [
        ['train', '16019d7e3df5f24257cddd939b257f8d'],
    ]
    test_list = [
        ['test', 'f0ef6b0ae62326f3e7ffdfab6717acfc'],
    ]
    meta = {
        'filename': 'meta',
        'key': 'fine_label_names',
        'md5': '7973b15100ade9c7d40fb424638fde48',
    }

"""**MODEL**"""

def conv3x3(in_planes, out_planes, stride=1):
    """3x3 convolution with padding"""
    return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride,
                     padding=1, bias=False)

class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super(BasicBlock, self).__init__()
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = nn.BatchNorm2d(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = nn.BatchNorm2d(planes)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            residual = self.downsample(x)

        out += residual
        out = self.relu(out)

        return out

class ResNet(nn.Module):

    def __init__(self, block, layers, num_classes=0): #SAREBBE num_classes=10
        self.inplanes = 16
        super(ResNet, self).__init__()
        self.conv1 = nn.Conv2d(3, 16, kernel_size=3, stride=1, padding=1,bias=False)
        self.bn1 = nn.BatchNorm2d(16)
        self.relu = nn.ReLU(inplace=True)
        self.layer1 = self._make_layer(block, 16, layers[0])
        self.layer2 = self._make_layer(block, 32, layers[1], stride=2)
        self.layer3 = self._make_layer(block, 64, layers[2], stride=2)
        self.avgpool = nn.AvgPool2d(8, stride=1)
        self.fc = nn.Linear(64 * block.expansion, num_classes)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes, planes * block.expansion,
                          kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(planes * block.expansion),
            )

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes))

        return nn.Sequential(*layers)

    def forward(self, x, toExtract):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)

        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        if toExtract==True:
          return x
        else:
          x = self.fc(x)
          return x

def resnet32(pretrained=False, **kwargs):
    n = 5
    model = ResNet(BasicBlock, [n, n, n], **kwargs)
    return model

"""**Set Argument**"""

DEVICE = 'cuda'    
BATCH_SIZE = 128
LR = 2         
NUM_EPOCHS = 70
MILESTONE=[49,63]
WEIGHT_DECAY = 0.00001 
GAMMA = 0.2
MOMENTUM=0.9

class iCaRLNet(nn.Module):
  def __init__(self):
    super(iCaRLNet, self).__init__()
    self.net = resnet32()        
    self.n_classes = 0
    self.n_known = 0
    self.classes_known=[]
    self.new_classes=[]
    self.dic={}
    self.count_per_dic=0
    
    self.loss=BCEWithLogitsLoss()
    
  def forward(self, x, toExtract=False):
    x = self.net(x, toExtract)
    return x

  @torch.no_grad()
  def classify(self,images):
    self.net.train(False)
    _, preds=torch.max(self.forward(images,False), dim=1)
    mapped=[]
    for pred in preds:
      mapped.append(list(self.dic.keys())[list(self.dic.values()).index(pred.item())]) 
    tensore=torch.tensor(mapped)
    return tensore

  def increment_classes(self, new_classes):
    self.new_classes=[]  
    for classe in new_classes:
      if classe not in self.classes_known:
        self.classes_known.append(classe)
        self.n_classes += 1
        self.new_classes.append(classe)
    in_features = self.net.fc.in_features
    out_features = self.net.fc.out_features
    weight = self.net.fc.weight.data
    bias = self.net.fc.bias.data
    self.net.fc = nn.Linear(in_features, out_features+len(self.new_classes), bias=True)
    self.net.fc.weight.data[:out_features] = weight    
    self.net.fc.bias.data[:out_features] = bias 
          
  def update_representation(self, dataset):
    
    classes = list(set(dataset.targets))
    self.increment_classes(classes)
    self.cuda()
    print ("Now there are %d classes" % (self.n_classes))
    
    optimizer = optim.SGD(self.net.parameters(), lr=LR, weight_decay=WEIGHT_DECAY,momentum=MOMENTUM)
    scheduler=optim.lr_scheduler.MultiStepLR(optimizer, milestones=MILESTONE, gamma=GAMMA)

    loader = torch.utils.data.DataLoader(dataset, batch_size=BATCH_SIZE,shuffle=True, num_workers=2)

    order_label=[]
    for i, (indices, images, labels) in enumerate(loader):
      for label in labels:
        if label not in order_label:
          order_label.append(label)      
          self.dic[label.item()]=self.count_per_dic
          self.count_per_dic +=1

    for epoch in range(NUM_EPOCHS):
      for i, (indices, images, labels) in enumerate(loader):
        indices = indices.cuda()
        images = images.cuda()
        labels = labels.cuda()

        mapped_labels=[]
        for label in labels:

          mapped_labels.append(self.dic[label.item()])

        oneHot=torch.nn.functional.one_hot(torch.tensor(mapped_labels),self.n_classes)
        oneHot=oneHot.type(torch.FloatTensor)
        oneHot=oneHot.cuda()
                
        self.net.train()
        optimizer.zero_grad()
        g = self.forward(images)
        lista_map=[]
        for classe in self.new_classes:
          lista_map.append(self.dic[classe])

        loss=self.loss(g[:,lista_map],oneHot[:,lista_map])

        loss.backward()
        optimizer.step()

        if (i+1) % 10 == 0:
          print(f"Epoch: {epoch+1}/{NUM_EPOCHS}, Iter: {i+1}/{math.ceil(len(dataset)/BATCH_SIZE)}, Loss: {loss.item():.4f}, lr={scheduler.get_last_lr()[0]} ")
      scheduler.step()

"""**MAIN**"""

def give_split():
  x=np.arange(0,100)
  x=x.tolist()
  random.seed(34)
  random.shuffle(x)
  total_classes=[]
  for i in range(0,100,10):
    lista=x[i:i+10]
    total_classes.append(lista)
  return total_classes

transform_train = transforms.Compose([
        transforms.RandomCrop(32, padding=4),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize((0.5071, 0.4867, 0.4408), (0.2675, 0.2565, 0.2761)),
])

transform_test = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.5071, 0.4867, 0.4408), (0.2675, 0.2565, 0.2761)),
])


icarl = iCaRLNet()
icarl.cuda()


list_classes=give_split()
lista_tot=[]

list_train_acc=[]
list_test_acc=[]

for s in range(0,len(list_classes)):
  for elem in list_classes[s]:
    lista_tot.append(elem)
  print("Loading training examples for classes", list_classes[s])

  print(f"In train {list_classes[s]}")
  print(f"In test {lista_tot}")
  train_set = iCIFAR100(root='./data',train=True,classes=list_classes[s],download=True,transform=transform_train)
  train_loader = torch.utils.data.DataLoader(train_set, batch_size=128,shuffle=True, num_workers=2)

  test_set = iCIFAR100(root='./data',train=False,classes=lista_tot,download=True,transform=transform_test)
  test_loader = torch.utils.data.DataLoader(test_set, batch_size=128,shuffle=False, num_workers=2)

  icarl.update_representation(train_set)


  icarl.n_known = icarl.n_classes


  icarl.net.train(False)
  total = 0.0
  correct = 0.0
  for indices, images, labels in train_loader:
    images = images.to(DEVICE)
    labels = labels.to(DEVICE)


    preds = icarl.classify(images).to(DEVICE)
    correct += torch.sum(preds == labels.data).data.item()
    total += labels.size(0)


  train_accuracy = correct / total
  print(f'Train Accuracy: {train_accuracy}')
  list_train_acc.append(train_accuracy)

  total = 0.0
  correct = 0.0
  for indices, images, labels in test_loader:
    images = images.to(DEVICE)
    labels = labels.to(DEVICE)

    preds = icarl.classify(images).to(DEVICE)
    
    correct += torch.sum(preds == labels.data).data.item()
    total += labels.size(0)

  test_accuracy = correct / total
  print(f'Test Accuracy: {test_accuracy}')
  list_test_acc.append(test_accuracy)

f = open("acc_train.txt", "w")
for el in list_train_acc:
  f.write(str(el)+"\n")
f.close()

f = open("acc_test.txt", "w")
for el in list_test_acc:
  f.write(str(el)+"\n")
f.close()

"""**CONFUSION MATRIX**"""

@torch.no_grad()
def get_all_preds(model, loader):
  all_preds = torch.tensor([])
  for indices, images, labels in loader:
    images = images.cuda()
    preds = icarl.classify(images).to(torch.float32)
    preds = preds.cuda()
    all_preds = torch.cat((all_preds.cuda(), preds), dim=0) #Concatenates the given sequence of seq tensors in the given dimension. 
                              #All tensors must either have the same shape (except in the concatenating dimension) or be empty.
                              #dim (int, optional) – the dimension over which the tensors are concatenated
  
  all_preds = all_preds.tolist()
  return all_preds

test_set = iCIFAR100(root='./data', train=False, classes=range(100), download=True, transform=transform_test)
with torch.no_grad():
  test_loader = torch.utils.data.DataLoader(test_set, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)
  test_preds = get_all_preds(icarl, test_loader)

cm = confusion_matrix(test_set.targets, test_preds, labels=lista_tot)
print(type(cm))
cm

def plot_confusion_matrix(cm, classes, normalize=False, title='Confusion matrix', cmap=plt.cm.jet):
  if normalize:
        # cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
    ones = np.ones(cm.shape)
    t = ones + cm
    cm = np.log(t)
        # ones = torch.ones(cm.shape, dtype=torch.float32)
        # cm = torch.log()
    print("Normalized confusion matrix")
  else:
    print('Confusion matrix, without normalization')

  # print(cm)
  plt.figure(figsize=(10,10))
  plt.imshow(cm, interpolation='nearest', cmap=cmap)
  # plt.title(title)
  # plt.colorbar()
    # tick_marks = np.arange(len(classes))
    # plt.xticks(tick_marks, classes, rotation=45)
    # plt.yticks(tick_marks, classes)

    # fmt = '.2f' if normalize else 'd'
    # thresh = cm.max() / 2.
    # for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
        # plt.text(j, i, format(cm[i, j], fmt), horizontalalignment="center", color="white" if cm[i, j] > thresh else "black")

  plt.tight_layout()
  plt.ylabel('True label')
  plt.xlabel('Predicted label')
  if normalize==True:
    plt.savefig("Confusion matrix Normalize")
  else:
    plt.savefig("Confusion matrix NOT Normalize")

plot_confusion_matrix(cm, test_set.classes, normalize=True)