import tensorflow as tf
import pickle
import numpy as np
import os 
import argparse

from dataGenerator import dataGenerator
from ratSimulator import RatSimulator
from agent import network
#HYPERPARAMETERS
LSTMUnits=128
linearLayerUnits=512
PlaceCells_units=256
HeadCells_units=12

learning_rate=1e-5
clipping=1e-5
weightDecay=1e-5
batch_size=10
epoches=750# (750*50*8)=300000
numberSteps=800
num_features=3 #num_features=[velocity, sin(angVel), cos(angVel)]

#Initialize place cells centers and head cells centers. Every time the program starts they are the same
rs=np.random.RandomState(seed=10)
#Generate 256 Place Cell centers
place_cell_centers=rs.uniform(0, 2.2 ,size=(PlaceCells_units,2))
#Generate 12 Head Direction Cell centers
head_cell_centers=rs.uniform(-np.pi,np.pi,size=(HeadCells_units))

#Number of trajectories to generate and use as data to train the network
trajectories=500
#Class that generate the trajectory and allows to compute the Place Cell and Head Cell distributions
dataGenerator=dataGenerator(numberSteps, num_features, PlaceCells_units, HeadCells_units)

global_step=0



def trainAgent(agent):
    global global_step
    #LOAD TESTING DATA
    if os.path.isfile("trajectoriesDataTesting.pickle"):
        print("Loading test data..")
        fileData=pickle.load(open("trajectoriesDataTesting.pickle","rb"))
        inputDataTest=fileData['X']
        posTest=fileData['pos']
        angleTest=fileData['angle']
    #Create new data
    else:
        print("Creating test data..")
        inputDataTest, posTest, angleTest=dataGenerator.generateData(batch_size=10)
        mydict={"X":inputDataTest,"pos":posTest, "angle":angleTest}
        with open('trajectoriesDataTesting.pickle', 'wb') as f:
            pickle.dump(mydict, f)

    init_LSTMStateTest=np.zeros((10,PlaceCells_units + HeadCells_units))
    init_LSTMStateTest[:, :PlaceCells_units]=dataGenerator.computePlaceCellsDistrib(posTest[:,0], place_cell_centers)
    init_LSTMStateTest[:, PlaceCells_units:]=dataGenerator.computeHeadCellsDistrib(angleTest[:,0], head_cell_centers)

    for epoch in range(epoches):
        #Create training Data
        inputData, pos, angle=dataGenerator.generateData(batch_size=trajectories)

        labelData=np.zeros((pos.shape[0], numberSteps, PlaceCells_units + HeadCells_units))
        for t in range(numberSteps):
            labelData[:,t, :PlaceCells_units]=dataGenerator.computePlaceCellsDistrib(pos[:,t], place_cell_centers)
            labelData[:,t, PlaceCells_units:]=dataGenerator.computeHeadCellsDistrib(angle[:,t], head_cell_centers)
        
        batches=int(inputData.shape[0]/batch_size)

        for startB in range(0, batches*batch_size, batch_size):
            endB=startB+batch_size
            #return a tensor of shape 10,800,3
            batchX=inputData[startB:endB]
            #return a tensor of shape 10,800,256+12
            batchY=labelData[startB:endB]
            #Retrieve data for initialize LSTM states
            #with shape 10,256+12
            batch_initLSTM=batchY[:,0]

            agent.training(batchX,batchY,batch_initLSTM, global_step)
            
            if (global_step%100==0):
                print(">>Testing the agent")
                agent.testing(inputDataTest, init_LSTMStateTest, posTest, place_cell_centers, global_step)

                print(">>Global step:",global_step,"Saving the model..")
                agent.save_restore_Model(restore=False, epoch=global_step)

            global_step+=1

def showGridCells(agent):
    num_traj=10000
    inputData=np.zeros((num_traj,numberSteps,3))
    positions=np.zeros((num_traj,numberSteps,2))
    angles=np.zeros((num_traj,numberSteps,1))
    env=RatSimulator(numberSteps)
    print(">>Generating trajectory")
    for i in range(num_traj):
        vel, angVel, pos, angle =env.generateTrajectory()
        inputData[i,:,0]=vel
        inputData[i,:,1]=np.sin(angVel)
        inputData[i,:,2]=np.cos(angVel)
        positions[i,:]=pos


    init_LSTMState=np.zeros((num_traj,PlaceCells_units + HeadCells_units))
    init_LSTMState[:, :PlaceCells_units]=dataGenerator.computePlaceCellsDistrib(positions[:,0], place_cell_centers)
    init_LSTMState[:, PlaceCells_units:]=dataGenerator.computeHeadCellsDistrib(angles[:,0], head_cell_centers)

    print(">>Computing Activity Map..")
    agent.showGridCells(inputData, init_LSTMState, positions)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("mode", help="train - will train the model \nshowcells - will create the activity maps of the neurons")
    args=parser.parse_args()
    with tf.Session() as sess:
        try:
            agent=network(sess, lr=learning_rate, hu=LSTMUnits, lu=linearLayerUnits, place_units=PlaceCells_units, head_units=HeadCells_units, clipping=clipping, weightDecay=weightDecay, batch_size=batch_size, num_features=num_features, n_steps=numberSteps)

            if(args.mode=="train"):
                if os.path.exists("agentBackup"):
                    print("Loading the model..")
                    agent.save_restore_Model(restore=True)
                    global_step=sess.run(agent.epoch)
                    print("Model loaded. Restarting from global step", global_step)
                
                trainAgent(agent)
            elif(args.mode=="showcells"):
                agent.save_restore_Model(restore=True)
                print("Model updated at global step:", sess.run(agent.epoch), "loaded")
                showGridCells(agent)
                
        except (KeyboardInterrupt,SystemExit):
            print("\n\nProgram shut down, saving the model..")
            agent.save_restore_Model(restore=False, epoch=global_step)
            print("\n\nModel saved!\n\n")
            raise