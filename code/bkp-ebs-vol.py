import json
import boto3
import logging
import os
from datetime import datetime
import time, dateutil
import math 
 

data_time_format = '%Y-%m-%d %H:%M:%S'
tz_est = dateutil.tz.gettz('America/New_York')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sts_client = boto3.client('sts', region_name = os.environ.get('AWS_REGION'))
ec2_client = boto3.client('ec2', region_name = os.environ.get('AWS_REGION'))
ec2_tag_name = os.environ.get("EC2_TAG_NAME")
ec2_tag_value = os.environ.get("EC2_TAG_VALUE")
current_account_id = sts_client.get_caller_identity()['Account']

def list_snapshots():
    try:
        custom_filter = [
                            {
                                'Name': 'status',
                                'Values': ['completed'] 
                            },
                            {
                                'Name': 'owner-id',
                                'Values': [str(current_account_id)]
                            }
                        ]
        
        response = ec2_client.describe_snapshots(Filters=custom_filter)
        
        snapshots_to_delete = []
        for snapshot in response['Snapshots']:
            logger.info(f"snapshot :: {json.dumps(snapshot,default=str)}")
            # snapshot_created_unix_time = time.mktime(datetime.strptime(snapshot['Tags'][0]['Value'],data_time_format).timetuple())
            snapshot_created_unix_time = [item['Value'] for item in snapshot['Tags'] if item['Key'] == 'CreatedTimestamp'][0]

            current_unix_time = time.time()
            
            logger.info(f"snapshot_created_unix_time = {snapshot_created_unix_time} - current_unix_time = {current_unix_time}")
            time_elapsed = current_unix_time - float(snapshot_created_unix_time)
            logger.info(f"time_elapsed = {time_elapsed}")
            if time_elapsed >= 604800.0:
                snapshots_to_delete.append(dict(SnapshotId=snapshot['SnapshotId'],CreatedAt=snapshot_created_unix_time,CurrentUnixTime=current_unix_time,TimeElapsed=time_elapsed))
        
        logger.info(f"Snapshots to be deleted : {json.dumps(snapshots_to_delete)}")
        
        snapshot_ids = [item["SnapshotId"] for item in snapshots_to_delete]
        return snapshot_ids
    except Exception as e:
        logger.error(f"list_snapshots :: Error describing snapshots: {str(e)}")


def delete_snapshots(snapshot_ids):
    try:
        deleted_snapshots = []
        for snapshot_id in snapshot_ids:
            response = ec2_client.delete_snapshot(SnapshotId=snapshot_id)
            
            if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                deleted_snapshots.append(snapshot_id)
        logger.info(f"Deleted snapshots : {deleted_snapshots}")
        return "success"
    except Exception as e:
        logger.error(f"delete_snapshots :: Error deleting snapshots: {str(e)}")
        return []  
         
def list_ec2_volumes(ec2_tag_name,ec2_tag_value):

    try:
        custom_filter = [
                            {
                                'Name': f'tag:{ec2_tag_name}',
                                'Values': [f'{ec2_tag_value}'] 
                            },
                        ]


        volumes = [volume for volume in ec2_client.describe_volumes(Filters=custom_filter)["Volumes"]]
        volume_ids = [attachment['Attachments'][0]['VolumeId'] for attachment in volumes if attachment['Attachments'][0]['State'] == "attached"]
        
        return volume_ids
    except Exception as e:
        logger.error(f"list_ec2_volumes :: Error listing EC2 Volumes: {str(e)}")
        return []

def create_snapshot(volume_ids):
    try:
        snapshots = []
        for volume_id in volume_ids:
            logger.info(f"Creating Snapshot for Volume Id : {volume_id}")
            current_date = datetime.now(tz=tz_est).strftime(data_time_format) 
            logger.info(f"current_date - {current_date}")
            response = ec2_client.create_snapshot(
                VolumeId=volume_id,
                Description=f'EC2 Snapshot for VolumeId : volume_id ',
                TagSpecifications=[
                    {
                        'ResourceType': 'snapshot',
                        'Tags': [
                            {
                                'Key': 'Name',
                                'Value': f"{current_date}"
                            },
                            {
                                'Key':'CreatedTimestamp',
                                'Value': str(time.time())
                            }
                        ]
    
                    }
                ]
            )
            
            if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                snapshots.append({key:val for key, val in response.items() if key != "ResponseMetadata"})

        logger.info(f"Snashots Created : {json.dumps(snapshots, default=str)}")
    except Exception as e:
        logger.error(f"create_snapshot :: Error creating snapshot: {str(e)}")

def lambda_handler(event, context):

    try:
        logger.info(f"event = {json.dumps(event)}")
        ## List the EBS Volumes
        volume_ids = list_ec2_volumes(ec2_tag_name,ec2_tag_value)
        logger.info(f"volume_ids = {volume_ids}")

        ## Get the list of available snapshots
        snapshot_ids = list_snapshots()
        logger.info(f"snapshot_ids to be deleted = {snapshot_ids}")

        ## Delete t he snapshots older than seven days
        if snapshot_ids:
            delete_snapshots(snapshot_ids)

        ## Create snapshots for the volumes
        if volume_ids:
            create_snapshot(volume_ids)
        
        return "success"
    except Exception as e:
        logger.error(f"lambda_handler :: Error in Lambda handler: {str(e)}")
        return e

