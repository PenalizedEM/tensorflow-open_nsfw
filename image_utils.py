VGG_MEAN = [104, 117, 123]


def create_yahoo_image_loader():
    """Yahoo open_nsfw image loading mechanism

    Approximation of the image loading mechanism defined in
    https://github.com/yahoo/open_nsfw/blob/master/classify_nsfw.py#L40
    """
    import numpy as np
    import skimage
    import skimage.io
    from PIL import Image
    from io import BytesIO

    def load_image(image_path):
        pimg = open(image_path, 'rb').read()

        img_data = pimg
        im = Image.open(BytesIO(img_data))

        if im.mode != "RGB":
            im = im.convert('RGB')

        imr = im.resize((256, 256), resample=Image.BILINEAR)

        fh_im = BytesIO()
        imr.save(fh_im, format='JPEG')
        fh_im.seek(0)

        image = skimage.img_as_float(skimage.io.imread(fh_im, as_grey=False)).astype(np.float32)

        H, W, _ = image.shape
        h, w = (224, 224)

        h_off = max((H - h) // 2, 0)
        w_off = max((W - w) // 2, 0)
        image = image[h_off:h_off + h, w_off:w_off + w, :]

        # RGB to BGR
        image = image[:, :, :: -1]

        image = image.astype(np.float32, copy=False)
        image = image * 255.0
        image -= np.array(VGG_MEAN, dtype=np.float32)

        image = np.expand_dims(image, axis=0)
        return image

    return load_image


def create_tensorflow_image_loader(session):
    """Tensorflow image loader

    Results seem to deviate quite a bit from yahoo image loader.
    (TODO: Find out why)
    Only support jpeg images.
    """
    import tensorflow as tf

    def load_image(image_path):
        image = tf.read_file(image_path)
        image = tf.image.decode_jpeg(image, channels=3)

        # rgb to bgr
        image = tf.reverse(image, [2])

        # isotropic rescale
        shape = tf.to_float(tf.shape(image)[:2])
        min_length = tf.minimum(shape[0], shape[1])
        new_shape = tf.to_int32((256 / min_length) * shape)
        image = tf.image.resize_images(image, (new_shape[0], new_shape[1]))

        # cropping
        offset = tf.to_int32((new_shape - 224) / 2)

        image = tf.image.crop_to_bounding_box(image, offset[0], offset[1],
                                              224, 224)

        image = tf.to_float(image) - VGG_MEAN

        image_batch = tf.expand_dims(image, axis=0)
        return session.run(image_batch)

    return load_image


def load_base64_tensor(_input):
    import tensorflow as tf

    def decode_and_crop(base64):
        _bytes = tf.decode_base64(base64)
        _image = tf.image.decode_jpeg(_bytes, channels=3,
                                      fancy_upscaling=False)
        _image = tf.image.convert_image_dtype(_image, tf.float32)
        _image = tf.image.resize_images(_image, [256, 256],
                                        method=tf.image.ResizeMethod.BILINEAR)
        _image = tf.image.crop_to_bounding_box(_image, 16, 16, 224, 224)

        return _image

    # we have to do some preprocessing with map_fn, since functions like
    # decode_*, resize_images and crop_to_bounding_box do not support
    # processing of batches
    image = tf.map_fn(decode_and_crop, _input,
                      back_prop=False, dtype=tf.float32)

    image = tf.image.convert_image_dtype(image, tf.uint8)

    image = tf.reverse(image, axis=[-1])
    image = tf.cast(image, dtype=tf.float32)
    image = tf.subtract(image, VGG_MEAN)

    return image
