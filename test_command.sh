export PROJECT_ID=tpu-prod-env-multipod

# export ACCELERATOR_TYPE=v5p-16
# export ZONE=us-east5-a
# export RUNTIME_VERSION=v2-alpha-tpuv5

export ACCELERATOR_TYPE=v4-8
export ZONE=us-central2-b
export RUNTIME_VERSION=tpu-ubuntu2204-base

# export ACCELERATOR_TYPE=v5litepod-16
# export ZONE=us-east5-b
# export RUNTIME_VERSION=v2-alpha-tpuv5-lite


export NODE_COUNT=8
export TPU_NAME=tonyjohnchen-tpu-${ACCELERATOR_TYPE}-${NODE_COUNT}slices-mtu9k
export NETWORK=${USER}-mtu9k

gcloud auth list
gcloud config set project ${PROJECT_ID}
gcloud config set compute/zone ${ZONE}

## Delete QR and TPU.
# yes | gcloud alpha compute tpus queued-resources delete $TPU_NAME --force


## Create single slice.
# TPU_NAME=tonyjohnchen-tpu-${ACCELERATOR_TYPE}-1slices-mtu9k
# gcloud alpha compute tpus queued-resources create ${TPU_NAME} \
# --node-id ${TPU_NAME} \
# --project ${PROJECT_ID} \
# --zone ${ZONE} \
# --network ${NETWORK} \
# --accelerator-type ${ACCELERATOR_TYPE} \
# --runtime-version ${RUNTIME_VERSION} --best-effort
# gcloud alpha compute tpus queued-resources list --filter=tonyjohnchen

## Create Multislice in mtu9k network
gcloud alpha compute tpus queued-resources create ${TPU_NAME} \
--node-prefix ${TPU_NAME} \
--node-count ${NODE_COUNT} \
--project ${PROJECT_ID} \
--zone ${ZONE} \
--network ${NETWORK} \
--accelerator-type ${ACCELERATOR_TYPE} \
--runtime-version ${RUNTIME_VERSION} --best-effort
gcloud alpha compute tpus queued-resources list --filter=tonyjohnchen


DATETIME=$(date +%Y-%m-%d-%H-%M-%S)
RUN_NAME=${USER}-mxla-steptime-debug-${ACCELERATOR_TYPE}-${NODE_COUNT}slices-${DATETIME}
python3 multihost_runner.py --TPU_PREFIX=$TPU_NAME \
--COMMAND="bash setup.sh MODE=nightly && sudo apt install numactl && dpkg -l | grep numactl; \
sudo bash MaxText/network_setting.sh; \
XLA_FLAGS=\"--xla_dump_to=/tmp/xla_dump/\" \
LIBTPU_INIT_ARGS=\"--xla_tpu_enable_megascale_barrier=true\" \
numactl --membind 0 --cpunodebind=0 --strict python3 MaxText/train.py MaxText/configs/base.yml run_name=$RUN_NAME \
base_output_directory=gs://tonyjohnchen-mxla-debug/ dataset_path=gs://max-datasets-rogue \
dataset_type=synthetic \
per_device_batch_size=6 reuse_example_batch=1 \
global_parameter_scale=1 \
metrics_file='metrics.txt' \
steps=20 enable_checkpointing=false enable_profiler=true profile_start_step=10 gcs_metrics=false && \
python3 end_to_end/eval_assert.py metrics_average metrics.txt 0.0 perf/step_time_seconds;"



TPU_NAME_ssh=$TPU_NAME-0
gcloud compute tpus tpu-vm ssh $TPU_NAME_ssh --zone=$ZONE --project=$PROJECT_ID

gs://tonyjohnchen-mxla-debug/10_steps_xplane