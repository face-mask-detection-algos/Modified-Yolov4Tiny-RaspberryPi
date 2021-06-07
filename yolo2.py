
from utils2 import cells_to_bboxes, non_max_suppression, NMS
from backbone import backbone
from CSP import ConvBlock
from PIL import Image
import torch.nn as nn
import torch
import numpy as np
from utils2 import use_gpu_if_possible, plot_image
from torchvision import transforms


class DecodeBox(nn.Module):

    def __init__(self, scaled_anchors, num_classes, img_size):
        super(DecodeBox, self).__init__()
        self.scaled_anchors = scaled_anchors
        self.num_anchors = len(scaled_anchors)
        self.num_classes = num_classes
        self.bbox_attrs = 5 + num_classes
        self.img_size = img_size

    def forward(self,input):

        batch_size = input.size(0)
        input_height = input.size(2)
        input_width = input.size(3)
        stride_h = self.img_size[1] / input_height
        stride_w = self.img_size[0] / input_width

        prediction = input

        x = torch.sigmoid(prediction[..., 0])
        y = torch.sigmoid(prediction[..., 1])
        w = prediction[..., 2]
        h = prediction[..., 3]
        conf = torch.sigmoid(prediction[..., 4])
        pred_cls = torch.sigmoid(prediction[..., 5:])
        FloatTensor = torch.FloatTensor
        LongTensor = torch.LongTensor

        grid_x = torch.linspace(0, input_width - 1, input_width).repeat(input_height, 1).repeat(
            batch_size * self.num_anchors, 1, 1).view(x.shape).type(FloatTensor)
        grid_y = torch.linspace(0, input_height - 1, input_height).repeat(input_width, 1).t().repeat(
            batch_size * self.num_anchors, 1, 1).view(y.shape).type(FloatTensor)
        anchor_w = FloatTensor(self.scaled_anchors).index_select(1, LongTensor([0]))
        anchor_h = FloatTensor(self.scaled_anchors).index_select(1, LongTensor([1]))
        anchor_w = anchor_w.repeat(batch_size, 1).repeat(1, 1, input_height * input_width).view(w.shape)
        anchor_h = anchor_h.repeat(batch_size, 1).repeat(1, 1, input_height * input_width).view(h.shape)
        pred_boxes = FloatTensor(prediction[..., :4].shape)

        pred_boxes[..., 0] = x.data + grid_x
        pred_boxes[..., 1] = y.data + grid_y
        pred_boxes[..., 2] = torch.exp(w.data) * anchor_w
        pred_boxes[..., 3] = torch.exp(h.data) * anchor_h
        scale = torch.Tensor([stride_w, stride_h] * 2).type(FloatTensor)
        output = torch.cat((pred_boxes.reshape(batch_size, -1, 4)*scale,
                            conf.reshape(batch_size, -1, 1), pred_cls.reshape(batch_size, -1, self.num_classes)), -1)
        return output.data





class Yolo(nn.Module):
    
           
    def __init__(self,in_channels,B,num_classes):
        super().__init__()
        self.back = backbone(in_channels)
        self.conv1 = ConvBlock(512,512,3,1)
        self.conv2 = ConvBlock(512,256,3,1)
        self.conv3 = nn.Conv2d(512,128,1,1)
        self.upsample = nn.ConvTranspose2d(128,256,2,2)
        self.conv4 = nn.Conv2d(256,255,1,1)
        self.conv5 = nn.Conv2d(512,255,1,1)
        self.head = nn.Conv2d(255,B*(5+num_classes),1,1)
        self.B = B

    def forward(self,x):
        out1 , out2 = self.back(x)
        out2 = self.conv1(out2)
        feat2 = out2
        out2 = self.conv3(out2)
        feat1 = torch.cat([out1,self.upsample(out2)],dim=1)
        feat2 = self.conv1(feat2)
        feat1 = self.conv2(feat1)
        feat1 = self.conv4(feat1)
        feat2 = self.conv5(feat2)
        return self.head(feat2).reshape(feat2.shape[0], self.B, 2 + 5, feat2.shape[2], feat2.shape[3]).permute(0, 1, 3, 4, 2),self.head(feat1).reshape(feat1.shape[0], self.B, 2 + 5, feat1.shape[2], feat1.shape[3]).permute(0, 1, 3, 4, 2)
    
    def detect_Persson(self,frame):
                
        ANCHORS =  [[(0.275 ,   0.320312), (0.068   , 0.113281), (0.017  ,  0.03   )], 
           [(0.03  ,   0.056   ), (0.01  ,   0.018   ), (0.006 ,   0.01    )]]
             
        S = [13,26]
        
        scaled_anchors = torch.tensor(ANCHORS) / (
        1 / torch.tensor(S).unsqueeze(1).unsqueeze(1).repeat(1, 3, 2))
        
        self.net=Yolo(3, 6//2, 2).eval()
        model_dict=torch.load("model_100_epochs.pt", map_location = use_gpu_if_possible())
        self.net.load_state_dict(model_dict)
        
        img = frame
        
        with torch.no_grad():

            out = self.net(img)
            boxes = []
            
            for i in range(2):
                anchor = scaled_anchors[i]
                print(anchor.shape)
                print(out[i].shape)
                boxes += cells_to_bboxes(out[i], S=out[i].shape[2], anchors = anchor)[0]
                
            boxes = non_max_suppression(boxes, iou_threshold=.8, threshold=.7, box_format = "midpoint")
            #boxes = NMS(boxes)
            print(boxes)
            
        return boxes           


if __name__ == '__main__':
    
    img = Image.open("0013.jpg").convert('RGB')
    x = transforms.ToTensor()(img).unsqueeze_(0)
    model = Yolo(3,3,2)
    boxes = model.detect_Persson(x)
    plot_image(img, boxes)
    #odel = Yolo(3,20,5)
    #out1,out2 = model(x)

    #print('out1 :',out1.shape,'out2:',out2.shape)