from LoRa import LoRa
class LoRaFactory:
   
    @staticmethod
    def create(sf=7,
                samp_rate=500000,
                preamb_len=8,
                pay_len=16,
                ldro=False,
                impl_head=False,
                has_crc=True,
                cr=2,
                center_freq=868.1e6,
                bw=125000,
                soft_decoding=False,
                coords=(0, 0, 0) ):
        

        return LoRa(sf, samp_rate, preamb_len, pay_len, ldro, impl_head, has_crc, cr, center_freq, bw, soft_decoding, coords)
