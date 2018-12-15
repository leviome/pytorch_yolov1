import torch
import numpy as np
from PIL import Image
import cv2
import os
from torch.utils import data

from data_process.data_aug import *
from data_process.bbox_util import *
import config


def norm_bb(size, b):
    x = b[:, 0:1]
    y = b[:, 1:2]

    dw = 1. / size[0]
    dh = 1. / size[1]

    x = (x * dw).clip(0.01, 0.99)
    y = (y * dh).clip(0.01, 0.99)
    w = ((b[:, 2:3] - b[:, 0:1]) * dw).clip(0.01, 0.99)
    h = ((b[:, 3:4] - b[:, 1:2]) * dh).clip(0.01, 0.99)

    return np.concatenate((x, y, w, h, b[:, 4:5]), axis=1)


def data_augment(fname, gt_path, data_aug):
    img = cv2.imread(fname, 1)[:, :, ::-1]
    bs = np.loadtxt(gt_path, delimiter=',').reshape((-1, 5))
    if data_aug:
        #assert bs.shape[0] > 0
        seq = Sequence([RandomHSV(40, 40, 30), RandomHorizontalFlip(0.5), RandomTranslate(0.2)])
        img, bs = seq(img.copy(), bs.copy())

    bs = norm_bb((img.shape[1], img.shape[0]), bs)
    return img, bs


class VOCDatasets(data.Dataset):
    def __init__(self, transform, list_file, box_encoder = None,train=False):

        self.transform = transform
        self.train = train
        self.label_path = []
        self.image_path = []
        self.box_encoder = box_encoder
        with open(list_file) as f:
            lines = f.readlines()

        self.num_samples = len(lines)

        for line in lines:
            splited = line.strip().split(' ')
            self.image_path.append(splited[0])
            self.label_path.append(splited[1])

    def __getitem__(self, idx):

        file_name = self.image_path[idx]
        gt_path = self.label_path[idx]

        img,bbox = data_augment(file_name,gt_path,self.train)

        #最大支持50个bbox

        if self.box_encoder is not None:
            gt = self.box_encoder(bbox)
        else:
            gt = np.zeros((50, 5), dtype=np.float32)
            gt[:len(bbox), :] = bbox
            gt = torch.from_numpy(gt).float()

        img = Image.fromarray(img)
        img = self.transform(img)

        return img,gt

    def __len__(self):
        return self.num_samples



if __name__ == '__main__':
    import tqdm
    from torchvision import transforms
    from box_utils import yolo_box_decoder,yolo_box_encoder,ssd_box_decoder,ssd_box_encoder
    class_num = 20
    transform = transforms.Compose([
        transforms.Resize([448, 448]),
        transforms.ToTensor(),
        # transforms.Normalize([0.485, 0.456, 0.406], [1, 1, 1])
    ])
    list_file = 'VOC2007_test.txt'

    dataset = VOCDatasets(transform,list_file ,ssd_box_encoder ,False)

    data_loader = data.DataLoader(dataset=dataset,
                                  batch_size=1,
                                  shuffle=False,
                                  num_workers=4)
    with open(list_file) as f:
        lines = f.readlines()
    prefix = 'results'
    outfile = 'voc'


    fps = [0] * class_num
    if not os.path.exists('results'):
        os.mkdir('results')
    for i in range(class_num):
        buf = '%s/%s%s.txt' % (prefix, outfile, config.classes[i])
        fps[i] = open(buf, 'w')

    #for img,box in tqdm.tqdm(data_loader):

    for lineId, (images, label) in tqdm.tqdm(enumerate(data_loader)):

        fileId = os.path.basename(lines[lineId]).split('.')[0]

        img = cv2.imread(lines[lineId].split(" ")[0])
        width, height = img.shape[1], img.shape[0]

        #pred_boxes,pred_conf = yolo_box_decoder(label)
        pred_boxes,pred_conf = ssd_box_decoder(label)
        #print(pred_boxes)
        for j in range(len(pred_boxes)):

            x1 = pred_boxes[j,0]
            y1 = pred_boxes[j,1]
            x2 = x1 + pred_boxes[j,2]
            y2 = y1 + pred_boxes[j,3]

            x1,x2 = int(x1*width),int(x2*width)
            y1,y2 = int(y1*height),int(y2*height)
            img = cv2.rectangle(img, (x1,y1), (x2,y2), (0, 0, 255), 5)

            #det_conf = pred_boxes[j, 4]
            #for k in range((len(pred_boxes[0]) - 5)):
                #cls_conf = pred_boxes[j, 5 + k]
            #    cls_id = k
            #    prob = float(det_conf * cls_conf)
            #    fps[cls_id].write('%s %f %f %f %f %f\n' % (fileId, prob, x1, y1, x2, y2))
            #print(pred_conf[j])

            for cls_id in range((len(pred_conf[j]))):
                #cls_id = k
                fps[cls_id].write('%s %f %f %f %f %f\n' % (fileId, pred_conf[j,cls_id], x1, y1, x2, y2))


    for i in range(class_num):
        fps[i].close()