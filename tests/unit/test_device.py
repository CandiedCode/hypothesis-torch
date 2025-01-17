"""Tests for the device strategy."""

import unittest

import hypothesis
import torch

import hypothesis_torch.device


class TestDevice(unittest.TestCase):
    """Tests for the device strategy."""

    @hypothesis.given(device=hypothesis_torch.device.device_strategy())
    def test_device_strategy(self, device: torch.device):
        """Test that the default arguments of device strategy can only generate physical, available devices."""
        self.assertIsInstance(device, torch.device)
        self.assertIn(device, hypothesis_torch.device.AVAILABLE_PHYSICAL_DEVICES)

    @hypothesis.given(hypothesis_torch.device.device_strategy(allow_meta_device=True))
    def test_device_strategy_with_meta_device(self, device: torch.device):
        """Test that the device strategy with allow_meta_device overridden to True can generate meta devices."""
        self.assertIsInstance(device, torch.device)
        self.assertIn(
            device,
            hypothesis_torch.device.AVAILABLE_PHYSICAL_DEVICES + hypothesis_torch.device.AVAILABLE_META_DEVICES,
        )

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA is not available")
    @hypothesis.given(hypothesis_torch.device.device_strategy(devices=hypothesis_torch.device.AVAILABLE_CUDA_DEVICES))
    def test_device_strategy_with_cuda_devices(self, device: torch.device):
        """Test the device strategy when specifying a list of CUDA devices only generates available CUDA devices."""
        self.assertIsInstance(device, torch.device)
        assert device in hypothesis_torch.device.AVAILABLE_CUDA_DEVICES

    @hypothesis.given(device=...)
    def test_device_strategy_from_type(self, device: torch.device):
        """Test that using the registered `torch.device` strategy gives a physical, available device."""
        self.assertIsInstance(device, torch.device)
        self.assertIn(device, hypothesis_torch.device.AVAILABLE_PHYSICAL_DEVICES)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA is not available")
    @hypothesis.given(device=...)
    def test_device_strategy_from_type_cuda(self, device: torch.cuda.device):
        """Test that using the registered `torch.cuda.device` strategy gives an available CUDA device."""
        self.assertIsInstance(device, torch.device)
        self.assertIn(device, hypothesis_torch.device.AVAILABLE_PHYSICAL_DEVICES)

    @hypothesis.given(device=hypothesis_torch.device.device_strategy(devices=[torch.device("cpu")]))
    def test_device_strategy_with_specified_devices(self, device: torch.device):
        """Test that the device strategy when specifying a list of devices only generates devices in that list."""
        self.assertIsInstance(device, torch.device)
        self.assertEqual(device, torch.device("cpu"))
