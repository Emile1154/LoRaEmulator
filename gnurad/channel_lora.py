#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: channelmodel
# Author: Emile
# GNU Radio version: 3.10.11.0

import os
import sys
sys.path.append(os.environ.get('GRC_HIER_PATH', os.path.expanduser('~/.grc_gnuradio')))

from LoRa import LoRa  # grc-generated hier_block
from gnuradio import blocks
from gnuradio import channels
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import threading
import numpy as np



class channel(gr.top_block):
    def __init__(self, tx: LoRa, rx: LoRa, noise_std=0.01, SNRdB = -5):
        gr.top_block.__init__(self, "channelmodel", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.tx = tx
        self.rx = rx
        self.noise_std = noise_std

        self.sf = rx.sf
        self.samp_rate = rx.samp_rate
        self.clk_offset = 0
        self.center_freq = rx.center_freq
        self.bw = rx.bw

        self.SNRdB = SNRdB


        self._check_lora_compatibility()

        self.channels_channel_model_0 = channels.channel_model(
            noise_voltage=(10**(-self.SNRdB/20)),
            frequency_offset=(self.center_freq*self.clk_offset*1e-6/self.samp_rate),
            epsilon=(1.0+self.clk_offset*1e-6),
            taps=[1.0 + 0.0j],
            noise_seed=0,
            block_tags=True
        )
        self.channels_channel_model_0.set_min_output_buffer(int(2**self.sf*self.samp_rate/self.bw*1.1))
        self.blocks_throttle_0 = blocks.throttle(gr.sizeof_gr_complex*1, (self.samp_rate*10), True)

       
        # Потоковые соединения
        self.connect((self.tx, 0), (self.blocks_throttle_0, 0))
        self.connect((self.blocks_throttle_0, 0), (self.channels_channel_model_0, 0))
        self.connect((self.channels_channel_model_0, 0), (self.rx, 0))
        # Path loss (умножение амплитуды на коэффициент затухания)
        # self.path_loss_block = blocks.multiply_const_cc(self._calculate_path_loss())
        # self.connect((self.channels_channel_model_0, 0), (self.path_loss_block, 0))
        

    def _calculate_path_loss(self):
        x1, y1, z1 = getattr(self.tx, 'coords', (0, 0, 0))
        x2, y2, z2 = getattr(self.rx, 'coords', (0, 0, 0))
        distance = np.sqrt((x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2)
        pl = 1.0 / (distance**2 + 1e-6)  # avoid div by zero
        pl *= np.random.normal(1.0, self.noise_std)
        return pl

    def _check_lora_compatibility(self):
        """Проверяем совпадение sf, cr, bw и других параметров"""
        attrs = ['sf', 'cr', 'bw', 'samp_rate', 'has_crc', 'impl_head', 'ldro']
        for attr in attrs:
            tx_val = getattr(self.tx, attr, None)
            rx_val = getattr(self.rx, attr, None)
            if tx_val != rx_val:
                raise ValueError(f"LoRa devices mismatch on {attr}: tx={tx_val}, rx={rx_val}")
            
    def get_sf(self):
        return self.sf

    def set_sf(self, sf):
        self.sf = sf

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.blocks_throttle_0.set_sample_rate((self.samp_rate*10))
        self.channels_channel_model_0.set_frequency_offset((self.center_freq*self.clk_offset*1e-6/self.samp_rate))

    def get_clk_offset(self):
        return self.clk_offset

    def set_clk_offset(self, clk_offset):
        self.clk_offset = clk_offset
        self.channels_channel_model_0.set_frequency_offset((self.center_freq*self.clk_offset*1e-6/self.samp_rate))
        self.channels_channel_model_0.set_timing_offset((1.0+self.clk_offset*1e-6))

    def get_center_freq(self):
        return self.center_freq

    def set_center_freq(self, center_freq):
        self.center_freq = center_freq
        self.channels_channel_model_0.set_frequency_offset((self.center_freq*self.clk_offset*1e-6/self.samp_rate))

    def get_bw(self):
        return self.bw

    def set_bw(self, bw):
        self.bw = bw

    def get_SNRdB(self):
        return self.SNRdB

    def set_SNRdB(self, SNRdB):
        self.SNRdB = SNRdB
        self.channels_channel_model_0.set_noise_voltage((10**(-self.SNRdB/20)))




# def main(top_block_cls=channel, options=None):
#     tb = top_block_cls()

#     def sig_handler(sig=None, frame=None):
#         tb.stop()
#         tb.wait()

#         sys.exit(0)

#     signal.signal(signal.SIGINT, sig_handler)
#     signal.signal(signal.SIGTERM, sig_handler)

#     tb.start()
#     tb.flowgraph_started.set()

#     try:
#         input('Press Enter to quit: ')
#     except EOFError:
#         pass
#     tb.stop()
#     tb.wait()


# if __name__ == '__main__':
#     main()
