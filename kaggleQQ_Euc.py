# Pre-requisites
import numpy as np
import pandas as pd
from collections import Counter
import re
import os
from sys import getsizeof
import time
import math
# import cv2

# To clear print buffer
# from IPython.display import clear_output

# tensorflow
import tensorflow as tf
# with tf.device('/gpu:0'):

# Keras
from keras import backend as K
from keras.models import Model, Sequential
from keras.layers import Input, Conv1D, MaxPooling1D, Merge
from keras.initializers import RandomNormal
from keras.layers import Flatten, Dense, Dropout, Lambda
from keras.layers.merge import Concatenate
from keras.layers.normalization import BatchNormalization
from keras.optimizers import SGD, RMSprop
from keras.callbacks import LearningRateScheduler, EarlyStopping, ModelCheckpoint

# PARAMETERS
MAX_NB_WORDS = 200000
inputLength = 1014  # input feature length (the paper used 1014)
validationSplit = 0.2
minibatchSize = 100
nEpochs = 100

# # Alphabet
# # Space is the first char because its index has to be 0
# alphabet = [' ', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p',
#             'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '0', '1', '2', '3', '4', '5', '6',
#             '7', '8', '9', '!', '^', '+', '-', '=']

# Load alphabet
alphabet = np.load("mathAlphabet.npy")
alphabet = [str(a) for a in alphabet]
print(alphabet)

# Params
inputDim = len(alphabet)  # number of letters (characters) in alphabet

EMBEDDING_FILE = '/home/voletiv/Downloads/GoogleNews-vectors-negative300.bin'

# LOAD TRAINING AND TESTING DATA

# Download train.csv and test.csv from
# https://www.kaggle.com/c/quora-question-pairs/
TRAIN_DATA_FILE = 'kaggleQuoraTrain.csv'
TEST_DATA_FILE = 'kaggleQuoraTest.csv'
trainDf = pd.read_csv(TRAIN_DATA_FILE, sep=',')
# testDf = pd.read_csv(TEST_DATA_FILE, sep=',')

# Check for any null values
print(trainDf.isnull().sum())
# print(testDf.isnull().sum())

# Add the string 'empty' to empty strings
trainDf = trainDf.fillna('empty')
# testDf = testDf.fillna('empty')

# Load idx of train and val
trainIdx = np.load("trainIdx.npy")
valIdx = np.load("valIdx.npy")


# To clean data
def text_to_wordlist(text, remove_stopwords=False, stem_words=False):
    # Clean the text, with the option to remove stopwords and to stem words.
    # Convert words to lower case and split them
    text = text.lower().split()
    # Optionally, remove stop words
    if remove_stopwords:
        stops = set(stopwords.words("english"))
        text = [w for w in text if not w in stops]
    text = " ".join(text)
    # Clean the text
    text = re.sub(r"[^A-Za-z0-9^,!.\/'+-=]", " ", text)
    text = re.sub(r"what's", "what is ", text)
    text = re.sub(r"\'s", " ", text)
    text = re.sub(r"\'ve", " have ", text)
    text = re.sub(r"can't", "cannot ", text)
    text = re.sub(r"n't", " not ", text)
    text = re.sub(r"i'm", "i am ", text)
    text = re.sub(r"\'re", " are ", text)
    text = re.sub(r"\'d", " would ", text)
    text = re.sub(r"\'ll", " will ", text)
    text = re.sub(r",", " ", text)
    text = re.sub(r"\.", " ", text)
    text = re.sub(r"!", " ! ", text)
    text = re.sub(r"\/", " ", text)
    text = re.sub(r"\^", " ^ ", text)
    text = re.sub(r"\+", " + ", text)
    text = re.sub(r"\-", " - ", text)
    text = re.sub(r"\=", " = ", text)
    text = re.sub(r"'", " ", text)
    text = re.sub(r"(\d+)(k)", r"\g<1>000", text)
    text = re.sub(r":", " : ", text)
    text = re.sub(r" e g ", " eg ", text)
    text = re.sub(r" b g ", " bg ", text)
    text = re.sub(r" u s ", " american ", text)
    text = re.sub(r"\0s", "0", text)
    text = re.sub(r" 9 11 ", "911", text)
    text = re.sub(r"e - mail", "email", text)
    text = re.sub(r"j k", "jk", text)
    text = re.sub(r"\s{2,}", " ", text)
    # Optionally, shorten words to their stems
    if stem_words:
        text = text.split()
        stemmer = SnowballStemmer('english')
        stemmed_words = [stemmer.stem(word) for word in text]
        text = " ".join(stemmed_words)
    # Return a list of words
    return(text)

# Clean text
print("Cleaning text...")
nOfTrainQs = len(trainDf['question1'])
trainFullQ1s = []
for i, q in enumerate(trainDf['question1']):
    print("Cleaning Train Q1s: {0:.2f}".format(
        float(i) / nOfTrainQs), end='\r')
    trainFullQ1s.append(text_to_wordlist(q))

trainFullQ2s = []
for i, q in enumerate(trainDf['question2']):
    print("Cleaning Train Q2s: {0:.2f}".format(
        float(i) / nOfTrainQs), end='\r')
    trainFullQ2s.append(text_to_wordlist(q))

# nOfTestQs = len(testDf['question1'])
# testQ1s = []
# for i, q in enumerate(testDf['question2']):
#     print("Cleaning Test Q1s: {0:.2f}".format(float(i) / nOfTestQs), end='\r')
#     testQ2s.append(text_to_wordlist(q))

# testQ2s = []
# for i, q in enumerate(testDf['question2']):
#     print("Cleaning Test Q2s: {0:.2f}".format(float(i) / nOfTestQs), end='\r')
#     testQ2s.append(text_to_wordlist(q))

print("Cleaned text.")

# Make train and val data
trainQ1s = [trainFullQ1s[i] for i in trainIdx]
trainQ2s = [trainFullQ2s[i] for i in trainIdx]
valQ1s = [trainFullQ1s[i] for i in valIdx]
valQ2s = [trainFullQ2s[i] for i in valIdx]

# Outputs (whether duplicate or not)
trainData = np.array(trainDf)
trainOutputs = trainData[trainIdx, 5]
valOutputs = trainData[valIdx, 5]


# To encode questions into char indices
def encodeQs(questions, inputLength, alphabet):
    # Initialize encoded questions array
    encodedQs = np.zeros((len(questions), inputLength), dtype='int32')
    # For each question
    for (q, question) in enumerate(questions):
        print(str(q) + " of " + str(len(questions)) + " = " +
              "{0:.2f}".format(float(q) / len(questions)), end='\r')
        # For each character in question, in reversed order (so latest
        # character is first)
        for (c, char) in enumerate(reversed(question[:inputLength])):
            # print(\"  \"+str(c))
            if char in alphabet:
                encodedQs[q][c] = alphabet.index(char)
            else:
                encodedQs[q][c] = 0
    print("Done encoding.")
    return encodedQs

# Make encoded questions out of training questions 1 and 2
print("encoding train qs - 1 of 2:")
encodedTrainQ1s = encodeQs(trainQ1s, inputLength, alphabet)
print("encoded train q1, encoding train q2:")
encodedTrainQ2s = encodeQs(trainQ2s, inputLength, alphabet)
print("encoded train q1 and q2")
print("encoding val qs - 1 of 2:")
encodedValQ1s = encodeQs(valQ1s, inputLength, alphabet)
print("encoded val q1, encoding val q2:")
encodedValQ2s = encodeQs(valQ2s, inputLength, alphabet)
print("encoded val q1 and q2")

# MODEL

# Inputs
inputA = Input(shape=(inputLength,), dtype='int32')
inputB = Input(shape=(inputLength,), dtype='int32')

# One hot encoding
oheInputA = Lambda(K.one_hot, arguments={
                   'num_classes': inputDim}, output_shape=(inputLength, inputDim))(inputA)
oheInputB = Lambda(K.one_hot, arguments={
                   'num_classes': inputDim}, output_shape=(inputLength, inputDim))(inputB)


def createBaseNetworkSmall(inputLength, inputDim):
    baseNetwork = Sequential()
    baseNetwork.add(Conv1D(256, 7, strides=1, padding='valid', activation='relu',  input_shape=(inputLength, inputDim),
                           kernel_initializer=RandomNormal(mean=0.0, stddev=0.05), bias_initializer=RandomNormal(mean=0.0, stddev=0.05)))
    baseNetwork.add(MaxPooling1D(pool_size=3, strides=3))
    baseNetwork.add(Conv1D(256, 7, strides=1, padding='valid', activation='relu', kernel_initializer=RandomNormal(
        mean=0.0, stddev=0.05), bias_initializer=RandomNormal(mean=0.0, stddev=0.05)))
    baseNetwork.add(MaxPooling1D(pool_size=3, strides=3))
    baseNetwork.add(Conv1D(256, 3, strides=1, padding='valid', activation='relu', kernel_initializer=RandomNormal(
        mean=0.0, stddev=0.05), bias_initializer=RandomNormal(mean=0.0, stddev=0.05)))
    baseNetwork.add(Conv1D(256, 3, strides=1, padding='valid', activation='relu', kernel_initializer=RandomNormal(
        mean=0.0, stddev=0.05), bias_initializer=RandomNormal(mean=0.0, stddev=0.05)))
    baseNetwork.add(Conv1D(256, 3, strides=1, padding='valid', activation='relu', kernel_initializer=RandomNormal(
        mean=0.0, stddev=0.05), bias_initializer=RandomNormal(mean=0.0, stddev=0.05)))
    baseNetwork.add(Conv1D(256, 3, strides=1, padding='valid', activation='relu', kernel_initializer=RandomNormal(
        mean=0.0, stddev=0.05), bias_initializer=RandomNormal(mean=0.0, stddev=0.05)))
    baseNetwork.add(MaxPooling1D(pool_size=3, strides=3))
    baseNetwork.add(Flatten())
    baseNetwork.add(Dense(1024, activation='relu'))
    baseNetwork.add(Dropout(0.5))
    baseNetwork.add(Dense(1024, activation='relu'))
    baseNetwork.add(Dropout(0.5))
    return baseNetwork

baseNetwork = createBaseNetworkSmall(inputLength, inputDim)

# because we re-use the same instance `base_network`,
# the weights of the network will be shared across the two branches
processedA = baseNetwork(oheInputA)
processedB = baseNetwork(oheInputB)


def euclidean_distance(vects):
    x, y = vects
    return K.sqrt(K.maximum(K.sum(K.square(x - y), axis=1, keepdims=True), K.epsilon()))


def eucl_dist_output_shape(shapes):
    shape1, shape2 = shapes
    return (shape1[0], 1)

distance = Lambda(euclidean_distance,
                  output_shape=eucl_dist_output_shape)([processedA, processedB])

model = Model([inputA, inputB], distance)

print(model.summary())


def contrastive_loss(y_true, y_pred):
    '''Contrastive loss from Hadsell-et-al.'06
    http://yann.lecun.com/exdb/publis/pdf/hadsell-chopra-lecun-06.pdf
    '''
    margin = 1
    return K.mean(y_true * K.square(y_pred) +
                  (1 - y_true) * K.square(K.maximum(margin - y_pred, 0)))


# Accuracy
def eucAcc(y_true, y_pred):
    thresh = 0.5
    return K.mean(K.equal(y_true, tf.to_float(K.less(y_pred, thresh))), axis=-1)


# Logloss
def eucLL(y_true, y_pred):
    myEps = 1e-15
    probs = K.maximum(K.minimum(y_pred, 1 - myEps), myEps)
    return K.mean(K.binary_crossentropy(probs, 1 - y_true), axis=-1)

# Compile
initLR = 0.001
momentum = 0.5
sgd = SGD(lr=initLR, momentum=momentum, decay=0, nesterov=False)
# rms = RMSprop()
model.compile(loss=contrastive_loss, optimizer=sgd, metrics=[eucAcc, eucLL])

# Model Checkpoint
filepath = "charCNN-maAl-smallLeCun-eucDist-val0.2-SGD-initLR0.001-epDrop2-epoch{epoch:02d}-tl{loss:.4f}-tacc{eucAcc:.4f}-tlogl{eucLL:.4f}-vl{val_loss:.4f}-vacc{val_eucAcc:.4f}-vlogl{val_eucLL:.4f}.hdf5"
checkpoint = ModelCheckpoint(
    filepath, verbose=1, save_best_only=False, save_weights_only=True)


# Halve lr every 3 epochs
def step_decay(epoch):
    initial_lrate = initLR
    drop = 0.5
    epochs_drop = 2.0
    lrate = initial_lrate * math.pow(drop, math.floor(epoch / epochs_drop))
    print("lr dropped to " + str(lrate))
    return lrate

lRate = LearningRateScheduler(step_decay)

# Callbacks
callbacks_list = [checkpoint, lRate]

# SKIP: Load weights
model.load_weights(
    "charCNN-maAl-smallLeCun-eucDist-val0.2-SGD-initLR0.001-epoch06-tl0.1907-tacc0.7109-tlogl0.5908-vl0.4764-vacc0.2433-vlogl1.3193.hdf5")

# Train
model.fit([encodedTrainQ1s, encodedTrainQ2s], trainOutputs,
          batch_size=minibatchSize, epochs=nEpochs, verbose=1,
          callbacks=callbacks_list, validation_data=(
    [encodedValQ1s, encodedValQ2s], valOutputs),
    initial_epoch=4)
