"""Strategies for generating Hugging Face transformers models."""

from __future__ import annotations

import transformers.activations
import inspect
from typing import TypeVar

import hypothesis
import hypothesis.strategies as st
import torch
import transformers

from hypothesis_torch import inspection_util

T = TypeVar("T")
TransformerType = TypeVar("TransformerType", bound=transformers.PreTrainedModel)

POSITIVE_INTS = st.integers(min_value=1, max_value=4)  # We intentionally limit positive ints for speed
FLOATS_BETWEEN_ZERO_AND_ONE = st.floats(
    min_value=0,
    max_value=1,
    allow_subnormal=False,
    allow_nan=False,
    allow_infinity=False,
)
FLOATS_GREATER_THAN_ZERO = st.floats(min_value=0, allow_subnormal=False, allow_nan=False, allow_infinity=False)
FLOATS_STRICTLY_GREATER_THAN_ZERO = st.floats(
    min_value=1e-6, allow_subnormal=False, allow_nan=False, allow_infinity=False, exclude_min=True
)
FLOATS_GREATER_THAN_ONE = st.floats(min_value=1, allow_subnormal=False, allow_nan=False, allow_infinity=False)


TRANSFORMER_CONFIG_KWARG_STRATEGIES = {
    "attention_bias": st.booleans(),
    "attention_dropout": FLOATS_BETWEEN_ZERO_AND_ONE,
    "bos_token_id": POSITIVE_INTS,
    "eos_token_id": POSITIVE_INTS,
    "hidden_act": st.sampled_from(["gelu", "relu", "silu", "gelu_new", "tanh"]),
    "activation": st.sampled_from(list(transformers.activations.ACT2FN.keys())),
    "activation_function": st.sampled_from(list(transformers.activations.ACT2FN.keys())),
    "projection_hidden_act": st.sampled_from(list(transformers.activations.ACT2FN.keys())),
    "hidden_size": POSITIVE_INTS,
    "initializer_range": FLOATS_STRICTLY_GREATER_THAN_ZERO,
    "intermediate_size": POSITIVE_INTS,
    "max_position_embeddings": POSITIVE_INTS,
    "num_attention_heads": POSITIVE_INTS,
    "num_hidden_layers": POSITIVE_INTS,
    "rms_norm_eps": FLOATS_GREATER_THAN_ZERO,
    "pretrained_tp": POSITIVE_INTS,
    "rope_theta": FLOATS_GREATER_THAN_ZERO,
    "num_embeddings": POSITIVE_INTS,
    "vocab_size": POSITIVE_INTS,
    "num_key_value_heads": POSITIVE_INTS,
    "sliding_window": POSITIVE_INTS,
    "esmfold_config": st.just(
        transformers.models.esm.configuration_esm.EsmFoldConfig()
    ),  # TODO: Support arbitrary ESMfoldConfig
    "use_timm_backbone": st.just(False),  # TODO: Support timm_backbone
    "dropout": FLOATS_BETWEEN_ZERO_AND_ONE,
    "classifier_dropout_prob": FLOATS_BETWEEN_ZERO_AND_ONE,
    "attention_probs_dropout_prob": FLOATS_BETWEEN_ZERO_AND_ONE,
    "hidden_dropout_prob": FLOATS_BETWEEN_ZERO_AND_ONE,
    "summary_first_dropout": FLOATS_BETWEEN_ZERO_AND_ONE,
    "contrastive_hidden_size": POSITIVE_INTS,
    "init_std": FLOATS_STRICTLY_GREATER_THAN_ZERO,
    "key_dim": st.tuples(POSITIVE_INTS, POSITIVE_INTS, POSITIVE_INTS).map(list),
    "hidden_sizes": st.tuples(POSITIVE_INTS, POSITIVE_INTS, POSITIVE_INTS).map(list),
    "depths": st.tuples(POSITIVE_INTS, POSITIVE_INTS, POSITIVE_INTS).map(list),
    "mlp_ratio": st.tuples(POSITIVE_INTS, POSITIVE_INTS, POSITIVE_INTS).map(list),
    "attention_ratio": st.tuples(POSITIVE_INTS, POSITIVE_INTS, POSITIVE_INTS).map(list),
    "drop_path_rate": FLOATS_BETWEEN_ZERO_AND_ONE,
    "pooling": st.sampled_from(["mean", "max"]),
    "spec_size": st.one_of(POSITIVE_INTS, st.tuples(POSITIVE_INTS, POSITIVE_INTS)),
    "patch_stride": st.one_of(POSITIVE_INTS, st.tuples(POSITIVE_INTS, POSITIVE_INTS)),
    "img_size": st.one_of(POSITIVE_INTS, st.tuples(POSITIVE_INTS, POSITIVE_INTS)),
    "logit_scale_init_value": FLOATS_STRICTLY_GREATER_THAN_ZERO,
}


def ignore_import_errors(func):
    """Decorator to ignore import errors."""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ImportError as e:
            hypothesis.note(f"Ignoring import error: {e}")
            hypothesis.assume(False)

    return wrapper


@st.composite
def build_from_cls_init(draw: st.DrawFn, cls: type[T], **kwargs) -> T:
    """Strategy for generating instances of a class by drawing values for its constructor.

    Args:
        draw: The draw function provided by `hypothesis`.
        cls: The class to generate an instance of.
        kwargs: Keyword arguments to pass to the constructor. If a keyword argument is a strategy, it will be drawn
            from.

    Returns:
        An instance of the class.

    """
    sig = inspection_util.infer_signature_annotations(cls.__init__)
    for param in sig.parameters.values():
        if param.name in kwargs and isinstance(kwargs[param.name], st.SearchStrategy):
            kwargs[param.name] = draw(kwargs[param.name])
        elif param.annotation is inspect.Parameter.empty:
            continue
        elif param.name in TRANSFORMER_CONFIG_KWARG_STRATEGIES:
            kwargs[param.name] = draw(TRANSFORMER_CONFIG_KWARG_STRATEGIES[param.name])
        elif "dropout" in param.name:
            kwargs[param.name] = draw(FLOATS_BETWEEN_ZERO_AND_ONE)
        elif param.annotation is int:
            kwargs[param.name] = draw(POSITIVE_INTS)
        else:
            kwargs[param.name] = draw(st.from_type(param.annotation))
    kwargs.pop("self", None)  # Remove self if a type was inferred

    # hidden_size must be divisible by num_heads
    if "hidden_size" in kwargs and "num_attention_heads" in kwargs:
        kwargs["hidden_size"] = kwargs["hidden_size"] * kwargs["num_attention_heads"]

    # pad_token_id must be less than vocab_size
    if "pad_token_id" in kwargs and "vocab_size" in kwargs:
        kwargs["pad_token_id"] = draw(st.integers(min_value=0, max_value=kwargs["vocab_size"] - 1))

    # Attention window (for LEDEncoder) must be even
    if "attention_window" in kwargs:
        kwargs["attention_window"] = kwargs["attention_window"] * 2

    # BridgeTowerConfig requires a `contrastive_hidden_size` parameter not included in its
    # TODO: Support BridgeTower

    # BitConfig requires a `layer_type` parameter of either "preactivation" or "bottleneck"
    if "Bit" in cls.__name__ and "layer_type" in kwargs:
        kwargs["layer_type"] = draw(st.sampled_from(["preactivation", "bottleneck"]))

    # Flaubert can only be used an encoder
    if "Flaubert" in cls.__name__ and "is_encoder" in kwargs:
        kwargs["is_encoder"] = True

    # Camembert can only be used as a decoder
    if "Camembert" in cls.__name__:
        kwargs["is_decoder"] = True

    # Flaubert requires pad_idx be less than n_words
    if "Flaubert" in cls.__name__:
        vocab_size = kwargs.get("vocab_size", kwargs.get("n_words"))
        kwargs["pad_index"] = draw(st.integers(min_value=0, max_value=vocab_size - 1))

    if "Levit" in cls.__name__:
        kwargs["num_attention_heads"] = (draw(st.tuples(POSITIVE_INTS, POSITIVE_INTS, POSITIVE_INTS).map(list)),)

    return cls(**kwargs)


@ignore_import_errors
@st.composite
def transformer_strategy(
    draw: st.DrawFn,
    cls: type[TransformerType] | st.SearchStrategy[type[TransformerType]],
    *,
    instantiate_weights: bool | st.SearchStrategy[bool] = True,
    **kwargs,
) -> TransformerType:
    """Strategy for generating Hugging Face transformers.

    Args:
        draw: The draw function provided by `hypothesis`.
        cls: The transformer class to generate.
        instantiate_weights: Whether to instantiate the weights of the transformer. If False, the transformer will be
            instantiated on the meta device. This is useful for testing uses of transformers models that do not require
            a forward pass.
        kwargs: Keyword arguments to pass to the transformer constructor. If a keyword argument is a strategy, it will
            be drawn from.

    Returns:
        A strategy for generating Hugging Face transformers.
    """
    if isinstance(cls, st.SearchStrategy):
        cls = draw(cls)
    assert issubclass(cls, transformers.PreTrainedModel)
    hypothesis.note(f"Building transformer from {cls.__name__}")
    config = draw(build_from_cls_init(cls.config_class, **kwargs))
    hypothesis.note(f"Building transformer ({cls.__name__}) with config {config}")

    if isinstance(instantiate_weights, st.SearchStrategy):
        instantiate_weights = draw(instantiate_weights)
    hypothesis.note(f"Instantiating weights: {instantiate_weights}")

    if instantiate_weights:
        return cls(config)
    with torch.device("meta"):
        return cls(config)
