
SAVE_ACCUMULATOR_ARRAY=("false" "true")
USE_RHS_NOISE_FUNCTION_ARRAY=("false" "true")
PRNG_KEY_ARRAY=(0)

for SAVE_ACCUMULATOR in ${SAVE_ACCUMULATOR_ARRAY[@]}; do
    for USE_RHS_NOISE_FUNCTION in ${USE_RHS_NOISE_FUNCTION_ARRAY[@]}; do
        for PRNG_KEY in ${PRNG_KEY_ARRAY[@]}; do
            RUN_NAME=mattdavidow-20230725-a2_ACCUMULATOR_${SAVE_ACCUMULATOR}_${USE_RHS_NOISE_FUNCTION}_PRNGKey_${PRNG_KEY}
            echo "${RUN_NAME}"
        done
    done
done
