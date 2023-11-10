# diagram.py
from diagrams import Diagram
from diagrams.aws.storage import ElasticBlockStoreEBSVolume,ElasticBlockStoreEBSSnapshot
from diagrams.aws.compute import LambdaFunction


with Diagram("Backup EC2 Volumes", show=False):
    LambdaFunction("Lambda") >> ElasticBlockStoreEBSVolume("EBS") >> ElasticBlockStoreEBSSnapshot("Snapshot")