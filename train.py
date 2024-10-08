import nobrainer
import tensorflow as tf
from pathlib import Path
import os
# TODO: argparse can be replaced by click
import argparse
import yaml


os.environ["CUDA_VISIBLE_DEVICES"]="0"

def main(config):

    """
    Train the brainy model
    """
    # Set parameters
    n_classes = config['train']['n_classes']
    batch_size = config['train']['dataset_train']['batch_size']
    v = config['train']['dataset_train']['volume_shape']
    b = config['train']['dataset_train']['block_shape']
    volume_shape = (v, v, v)
    block_shape = (b, b, b)
    n_epochs = config['train']['training']['epoch']
    n_train = config['train']['dataset_train']['n_train'] #ToDo: it is required when using user data
    n_eval = config['train']['dataset_test']['n_test'] #ToDo: it is required when using user data
    
    if config.get("data_train_pattern") and config.get("data_valid_pattern"):
        data_train_pattern = config["data_train_pattern"]
        data_evaluate_pattern = config["data_valid_pattern"]
        if (data_train_pattern.split(".")[-1] not in ["tfrec", "tfrecord"])\
                or (data_evaluate_pattern.split(".")[-1] not in ["tfrec", "tfrecord"]):
            # TODO: write tfrecords from csv file given by user
            raise ValueError("can't use non-tfrecord format data."
                             "convert your data in the form of tfrecords with"
                             "'nobrainer.tfrecord.write'")
    else: # using sample data if no patterns provided by the user
        # checking sample_data from the config file
        if config['train'].get("sample_data") != 'sample_MGH':
            raise ValueError(f"only sample_MGH can be used as sample_data, "
                             f"but {config['train'].get('sample_data')} provided")
        #Load sample Data--- inputs and labels 
        csv_of_filepaths = nobrainer.utils.get_data()
        filepaths = nobrainer.io.read_csv(csv_of_filepaths)
        train_paths = filepaths[:9]
        evaluate_paths = filepaths[9:]
        
        invalid = nobrainer.io.verify_features_labels(train_paths, num_parallel_calls=2)
        assert not invalid
        invalid = nobrainer.io.verify_features_labels(evaluate_paths)
        assert not invalid
        
        data_dir = Path(config['train']["dataset_train"]["data_location"])
        os.makedirs(data_dir, exist_ok=True)
        
        nobrainer.tfrecord.write(
            features_labels=train_paths,
            filename_template= str(data_dir / "data-train_shard-{shard:03d}.tfrec"),
            examples_per_shard=3)
        
        data_train_pattern = str(data_dir / "data-train_shard-*.tfrec")
        
        nobrainer.tfrecord.write(
            features_labels=evaluate_paths,
            filename_template= str(data_dir / 'data-evaluate_shard-{shard:03d}.tfrec'),
            examples_per_shard=1)
        
        data_evaluate_pattern = str(data_dir / "data-evaluate_shard-*.tfrec")
       
    # Create and Load Datasets for training and validation
    dataset_train = nobrainer.dataset.Dataset.from_tfrecords(
        file_pattern = data_train_pattern,
        n_classes = n_classes,
        volume_shape = volume_shape,
        block_shape = block_shape,
        num_parallel_calls = config['train']['dataset_train']['num_parallel_calls'],
    )

    dataset_train.\
        shuffle(10).\
        repeat(n_epochs)
    
    dataset_evaluate = nobrainer.dataset.Dataset.from_tfrecords(
        file_pattern = data_evaluate_pattern,
        n_classes = n_classes,
        volume_shape = volume_shape,
        block_shape = block_shape,
        num_parallel_calls = config['train']['dataset_test']['num_parallel_calls'],
    )

    dataset_evaluate.repeat(1)
    
    # TODO: Add multi gpu training option
    # Compile model
    model = nobrainer.models.meshnet(n_classes=n_classes, 
                                  input_shape=(*block_shape, 1), receptive_field=129)


    optimizer = tf.keras.optimizers.Adam(learning_rate = config['train']['training']['lr'])
    model.compile(optimizer=optimizer,
                  loss= eval(config['train']['training']['loss']),
                  metrics= [eval(x) for x in config['train']['training']['metrics']],)
    
    """ # Training Model
    steps_per_epoch = nobrainer.dataset.get_steps_per_epoch(
        n_volumes=n_train,
        volume_shape=volume_shape,
        block_shape=block_shape,
        batch_size=batch_size)
    
    print("number of steps per training epoch:", steps_per_epoch)
    
    validation_steps = nobrainer.dataset.get_steps_per_epoch(
        n_volumes=n_eval,
        volume_shape=volume_shape,
        block_shape=block_shape,
        batch_size=batch_size)
    
    print("number of steps per validation epoch:", validation_steps) """
    # TODO: implement callbacks
    # callbacks = []
    # if check_point_path:
    #     cpk_call_back = tf.keras.callbacks.ModelCheckpoint(check_point_path)
    #     callbacks.append(cpk_call_back)
        
    # history = model.fit(
    model.fit(
            dataset_train.dataset,
            epochs= n_epochs,
            steps_per_epoch=n_epochs // batch_size, 
            validation_data=dataset_evaluate.dataset, 
            #validation_steps=validation_steps,
            #callbacks=callbacks,
            )
    
    # TODO: save the training history
    # if save_history:
    #     current_directory = os.getcwd()
    #     file_name = os.pathjoin(current_directory,f"{save_history}.json")
    #     with open(file_name,"w") as file:
    #         json.dump(history, file)
            
    #save model
    save_path = Path(config['train']['path']['save_model'])
    os.makedirs(save_path, exist_ok=True)
    
    model.save_weights(str(save_path / 'weights_brainy_unet.h5'))
    print("The trained model is saved at {}".format(str(save_path / 'weights_brainy_unet.h5')))
    
    # TODO: Add loading a pretrained model for transfer learning 
        
if __name__ == '__main__':
    
    config = "spec.yaml"
    with open(config, 'r') as stream:
        config = yaml.safe_load(stream)
    main(config)

