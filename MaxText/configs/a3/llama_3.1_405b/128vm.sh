echo "Running 128vm.sh"
# Example command to invoke this script via XPK
# python3 xpk/xpk.py workload create --cluster ${CLUSTER_NAME} \
# --workload ${WORKLOAD_NAME} --docker-image=gcr.io/supercomputer-testing/${LOCAL_IMAGE_NAME} \
# --device-type ${DEVICE_TYPE} --num-slices 128 --priority=high \
# --command "bash MaxText/configs/a3/llama_3.1_405b/128vm.sh"

# Stop execution if any command exits with error
set -e

export OUTPUT_PATH="gs://maxtext-experiments-multipod"
export RUN_NAME="llama-3.1-128vm-$(date +%Y-%m-%d-%H-%M)"
export EXECUTABLE="train.py"

# Set environment variables
for ARGUMENT in "$@"; do
    IFS='=' read -r KEY VALUE <<< "$ARGUMENT"
    export "$KEY"="$VALUE"
done

export XLA_FLAGS="--xla_dump_to=$OUTPUT_PATH/$RUN_NAME/HLO_dumps/
--xla_gpu_enable_latency_hiding_scheduler=true \
--xla_gpu_enable_triton_gemm=false \
--xla_gpu_enable_highest_priority_async_stream=true \
--xla_gpu_all_reduce_combine_threshold_bytes=134217728 \
--xla_gpu_all_gather_combine_threshold_bytes=1073741824 \
--xla_gpu_reduce_scatter_combine_threshold_bytes=33554432 \
--xla_gpu_enable_pipelined_all_gather=true \
--xla_gpu_enable_pipelined_reduce_scatter=true \
--xla_gpu_enable_pipelined_all_reduce=true \
--xla_gpu_enable_while_loop_double_buffering=true \
--xla_gpu_enable_triton_softmax_fusion=false \
--xla_gpu_enable_all_gather_combine_by_dim=false \
--xla_gpu_enable_reduce_scatter_combine_by_dim=false \
--xla_disable_hlo_passes=rematerialization"

# --xla_gpu_enable_latency_hiding_scheduler=true
# --xla_gpu_enable_triton_gemm=false --xla_gpu_graph_level=0
# --xla_gpu_enable_highest_priority_async_stream=true
# --xla_gpu_all_reduce_combine_threshold_bytes=1073741824 --xla_gpu_all_gather_combine_threshold_bytes=134217728
# --xla_gpu_reduce_scatter_combine_threshold_bytes=134217728 --xla_gpu_enable_pipelined_all_gather=true
# --xla_gpu_enable_pipelined_reduce_scatter=true --xla_gpu_enable_pipelined_all_reduce=true
# --xla_gpu_enable_while_loop_double_buffering=true --xla_gpu_enable_triton_softmax_fusion=false
# --xla_gpu_enable_all_gather_combine_by_dim=false --xla_gpu_enable_reduce_scatter_combine_by_dim=false
# --xla_disable_hlo_passes=rematerialization

# 128 nodes
python MaxText/$EXECUTABLE MaxText/configs/models/gpu/llama3.1_405b.yml run_name=$RUN_NAME \
    dcn_data_parallelism=1 ici_fsdp_parallelism=128 base_output_directory=$OUTPUT_PATH profiler=xplane