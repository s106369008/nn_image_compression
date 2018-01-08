import numpy as np
import canton as ct
from canton import *
import tensorflow as tf

from train import *

# apply VGG16 to a tensor, obtain output from one of the layers
def apply_vgg(tensor):
    print('importing VGG16...')
    from keras.applications.vgg16 import VGG16
    from keras import backend as K
    K.set_session(ct.get_session()) # make sure we are in the same universe

    vgginst = VGG16(include_top=False, weights='imagenet', input_tensor=tensor)
    return vgginst.get_layer('block1_conv2').output

def get_trainer():
    x = ph([None,None,3])

    # augment the training set by adding random gain and bias perturbation
    sx = tf.shape(x)
    input_gain = tf.random_uniform(
        minval=0.6,
        maxval=1.4,
        shape=[sx[0],1,1,1])
    input_bias = tf.random_uniform(
        minval=-.2,
        maxval=.2,
        shape=[sx[0],1,1,1])
    pt_x = x * input_gain + input_bias
    pt_x = tf.clip_by_value(pt_x,clip_value_max=1.,clip_value_min=0.)

    code_noise = tf.Variable(0.1)
    linear_code = enc(pt_x)

    # add gaussian before sigmoid to encourage binary code
    noisy_code = linear_code + \
        tf.random_normal(stddev=code_noise,shape=tf.shape(linear_code))
    binary_code = Act('sigmoid')(noisy_code)

    y = dec(binary_code)

    perceptual_y = apply_vgg(y)
    perceptual_x = apply_vgg(pt_x)


    # use this loss for initialization
    loss_init = tf.reduce_mean((y-pt_x)**2)
    # use this loss after initialization
    loss = tf.reduce_mean((perceptual_x-perceptual_y)**2) * 0.00\
        + tf.reduce_mean((y-pt_x)**2) \
        + tf.reduce_mean(binary_code) * 0.01 * code_noise

    opt = tf.train.AdamOptimizer(learning_rate=1e-4)
    
    train_step_init = opt.minimize(loss_init,
    var_list=enc.get_weights()+dec.get_weights())
    
    train_step = opt.minimize(loss,
        var_list=enc.get_weights()+dec.get_weights())

    def feed(batch,cnoise,init=False):
        sess = ct.get_session()
        if init:
            res = sess.run([train_step_init,loss_init],feed_dict={
                x:batch,
                code_noise:cnoise,
            })
        else:
            res = sess.run([train_step,loss],feed_dict={
                x:batch,
                code_noise:cnoise,
            })

        return res[1]

    set_training_state(False)
    quantization_threshold = tf.Variable(0.5)
    binary_code_test = tf.cast(binary_code>quantization_threshold,tf.float32)
    y_test = dec(binary_code_test)

    def test(batch,quanth):
        sess = ct.get_session()
        res = sess.run([binary_code_test,y_test,binary_code,y,pt_x],feed_dict={
            x:batch,
            quantization_threshold:quanth,
        })
        return res
    return feed,test

feed,test = get_trainer()
get_session().run(ct.gvi())

def r(ep=1,cnoise=0.1,init=False):
    np.random.shuffle(xt)
    length = len(xt)
    bs = 20
    for i in range(ep):
        print('ep',i)
        for j in range(0,length,bs):
            minibatch = xt[j:j+bs]
            loss = feed(minibatch,cnoise,init=init)
            print(j,'loss:',loss)

            if j%100==0:
                show()

def show(threshold=.5):
    from cv2tools import vis,filt
    import math
    
    bs = 16
    j = np.random.choice(len(xt)-16)
    minibatch = xt[j:j+bs]
    code, rec, code2, rec2, noisy_x = test(minibatch,threshold)

    code = np.transpose(code[0:1],axes=(3,1,2,0))
    code2 = np.transpose(code2[0:1],axes=(3,1,2,0))

    vis.show_batch_autoscaled(code, name='code(quant)', limit=600.)
    vis.show_batch_autoscaled(code2, name='code2(no quant)', limit=600.)

    vis.show_batch_autoscaled(noisy_x,name='input')
    vis.show_batch_autoscaled(rec,name='recon(quant)')
    vis.show_batch_autoscaled(rec2,name='recon(no quant)')

    mse=noisy_x-rec2
    
    #print(mse)
    sq_mse=np.power(mse,2)
    #abs_mse=abs(mse)
    print("******************")
    #print(sq_mse)
    sum_sq_error=sq_mse.sum()
    #print (sum_sq_error)
    #print("legth")
    #print(len(noisy_x[0][0]))
    print("MSE=")
    mean=sum_sq_error/(32*32*16)
    print(mean)
    #mean=

show()