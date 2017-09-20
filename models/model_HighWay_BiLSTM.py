import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
import numpy as np
import random
import torch.nn.init as init
import hyperparams
torch.manual_seed(hyperparams.seed_num)
random.seed(hyperparams.seed_num)


class HighWay_BiLSTM(nn.Module):
    def __init__(self, args):
        super(HighWay_BiLSTM, self).__init__()
        self.args = args
        self.hidden_dim = args.lstm_hidden_dim
        self.num_layers = args.lstm_num_layers
        V = args.embed_num
        D = args.embed_dim
        C = args.class_num
        self.dropout = nn.Dropout(args.dropout)
        if args.max_norm is not None:
            print("max_norm = {} ".format(args.max_norm))
            self.embed = nn.Embedding(V, D, max_norm=args.max_norm)
        else:
            print("max_norm = {} |||||".format(args.max_norm))
            self.embed = nn.Embedding(V, D)
        if args.word_Embedding:
            pretrained_weight = np.array(args.pretrained_weight)
            self.embed.weight.data.copy_(torch.from_numpy(pretrained_weight))
        self.bilstm = nn.LSTM(D, self.hidden_dim, num_layers=self.num_layers, bias=True, bidirectional=True,
                              dropout=self.args.dropout)
        print(self.bilstm)
        if args.init_weight:
            print("Initing W .......")
            init.xavier_normal(self.bilstm.all_weights[0][0], gain=np.sqrt(args.init_weight_value))
            init.xavier_normal(self.bilstm.all_weights[0][1], gain=np.sqrt(args.init_weight_value))
            init.xavier_normal(self.bilstm.all_weights[1][0], gain=np.sqrt(args.init_weight_value))
            init.xavier_normal(self.bilstm.all_weights[1][1], gain=np.sqrt(args.init_weight_value))

        # self.hidden2label1 = nn.Linear(in_features=self.hidden_dim * 2, out_features=C, bias=True)
        self.hidden2label1 = nn.Linear(in_features=self.hidden_dim * 2, out_features=self.hidden_dim * 2, bias=True)
        # self.hidden2label2 = nn.Linear(self.hidden_dim, C)

        # highway gate layer
        # self.gate_layer = nn.Linear(in_features=self.hidden_dim * 2, out_features=C, bias=True)
        self.gate_layer = nn.Linear(in_features=self.hidden_dim * 2, out_features=self.hidden_dim * 2, bias=True)

        # last liner
        self.logit_layer = nn.Linear(in_features=self.hidden_dim * 2, out_features=C, bias=True)

        self.hidden = self.init_hidden(self.num_layers, args.batch_size)
        print("self.hidden", self.hidden)


    def init_hidden(self, num_layers, batch_size):
        # the first is the hidden h
        # the second is the cell  c
        return (Variable(torch.zeros(2 * num_layers, batch_size, self.hidden_dim)),
                Variable(torch.zeros(2 * num_layers, batch_size, self.hidden_dim)))

    def forward(self, x):
        x = self.embed(x)
        x = self.dropout(x)
        bilstm_out, self.hidden = self.bilstm(x, self.hidden)

        bilstm_out = torch.transpose(bilstm_out, 0, 1)
        bilstm_out = torch.transpose(bilstm_out, 1, 2)
        # bilstm_out = F.max_pool1d(bilstm_out, bilstm_out.size(2)).squeeze(2)
        bilstm_out = F.max_pool1d(bilstm_out, bilstm_out.size(2))
        bilstm_out = bilstm_out.squeeze(2)

        hidden2lable = self.hidden2label1(F.tanh(bilstm_out))

        gate_layer = F.sigmoid(self.gate_layer(bilstm_out))
        # calculate highway layer values
        gate_hidden_layer = torch.mul(hidden2lable, gate_layer)
        # if write like follow ,can run,but not equal the HighWay NetWorks formula
        # gate_input = torch.mul((1 - gate_layer), hidden2lable)
        gate_input = torch.mul((1 - gate_layer), bilstm_out)
        highway_output = torch.add(gate_hidden_layer, gate_input)

        logit = self.logit_layer(highway_output)

        return logit