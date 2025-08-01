#
# Copyright (c) 2025 Huawei Technologies Co., Ltd. All Rights Reserved.
# Copyright 2023 The vLLM team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
Compare the outputs of vLLM with and without aclgraph.

Run `pytest tests/compile/test_aclgraph.py`.
"""

import pytest
import torch
from vllm import LLM, SamplingParams

from tests.e2e.conftest import VllmRunner
from tests.e2e.model_utils import check_outputs_equal

MODELS = [
    "Qwen/Qwen2.5-0.5B-Instruct",
    # TODO: REVERT ME when oom is fixed
    # "vllm-ascend/Qwen3-30B-A3B-Puring"
]


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("max_tokens", [32])
def test_models_with_aclgraph(
    model: str,
    max_tokens: int,
) -> None:
    prompts = [
        "Hello, my name is", "The president of the United States is",
        "The capital of France is", "The future of AI is"
    ]

    sampling_params = SamplingParams(max_tokens=max_tokens, temperature=0.0)
    # TODO: change to use vllmrunner when the registry of custom op is solved
    # while running pytest
    vllm_model = LLM(model, max_model_len=1024)
    vllm_aclgraph_outputs = vllm_model.generate(prompts, sampling_params)
    del vllm_model
    torch.npu.empty_cache()

    vllm_model = LLM(model, enforce_eager=True, max_model_len=1024)
    vllm_eager_outputs = vllm_model.generate(prompts, sampling_params)
    del vllm_model
    torch.npu.empty_cache()

    vllm_aclgraph_outputs_list = []
    for output in vllm_aclgraph_outputs:
        vllm_aclgraph_outputs_list.append(
            (output.outputs[0].index, output.outputs[0].text))

    vllm_eager_outputs_list = []
    for output in vllm_eager_outputs:
        vllm_eager_outputs_list.append(
            (output.outputs[0].index, output.outputs[0].text))

    check_outputs_equal(
        outputs_0_lst=vllm_eager_outputs_list,
        outputs_1_lst=vllm_aclgraph_outputs_list,
        name_0="vllm_eager_outputs",
        name_1="vllm_aclgraph_outputs",
    )


def test_deepseek_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as m:
        m.setenv("VLLM_USE_MODELSCOPE", "True")
        with pytest.raises(NotImplementedError) as excinfo:
            VllmRunner("deepseek-ai/DeepSeek-V2-Lite-Chat",
                       max_model_len=1024,
                       enforce_eager=False)
        assert "ACL Graph does not support deepseek" in str(excinfo.value)


@pytest.mark.parametrize("model", MODELS)
def test_ray_backend_sets_no_compilation(model: str) -> None:
    runner = VllmRunner(model,
                        enforce_eager=False,
                        distributed_executor_backend="ray")
    assert runner.model.llm_engine.vllm_config.compilation_config.level == 0
