import pmt
from LoRa import LoRa
from gnuradio import gr, blocks, channels
import threading
from channel_lora import channel
import signal
from LoRaFactory import LoRaFactory
import sys
import time
class LoRaRuntime(channel):  # наследуемся от channel
    def __init__(self, tx: LoRa, rx: LoRa, noise_std=0.01, SNRdB=-5):
        super().__init__(tx=tx, rx=rx, noise_std=noise_std, SNRdB=SNRdB)

class MsgPrinter(gr.basic_block):
    def __init__(self):
        gr.basic_block.__init__(self,
                               name="MsgPrinter",
                               in_sig=None,
                               out_sig=None)
        # регистрируем входной message port (имя — PMT symbol)
        self.message_port_register_in(pmt.intern("in"))
        # ставим обработчик, который будет вызываться при получении PMT
        self.set_msg_handler(pmt.intern("in"), self.msg_callback)

    def msg_callback(self, pmt_msg):
        # ожидаем, что pmt_msg — u8vector или u8vector в cdr/car
        try:
            # если это просто u8vector
            data = bytes(pmt.u8vector_elements(pmt_msg))
        except Exception:
            # если это PDU (pair (meta, payload))
            if pmt.is_pair(pmt_msg):
                payload = pmt.cdr(pmt_msg)
                data = bytes(pmt.u8vector_elements(payload))
            else:
                data = b''
        print("[MsgPrinter] received:", data)

# runtime
def main():
    # Создаём устройства
    tx = LoRaFactory.create()
    rx = LoRaFactory.create()

    tb = channel(tx=tx, rx=rx, noise_std=0.01, SNRdB=-5)

    # Создаём MsgPrinter (basic_block)
    # printer = MsgPrinter()

  
    # tb.msg_connect((rx, 'msg_rx'), (printer, 'in'))

    # Теперь printer — простой basic_block, но он должен быть частью flowgraph,
    # поэтому подключаем его к top_block как "stream" no-op (ничего не нужно для stream ports),
    # однако msg_connect уже делает связь сообщений — достаточно добавить блок в graph,
    # чтобы он участвовал в lifecycle (start/stop). Для этого можно просто вызвать:
    # tb.connect не нужен для message-порта; но basic_block должен быть добавлен в graph:
    # simplest way: connect printer to a null_sink to satisfy stream API? Нет — для basic_block
    # с no stream портами это не нужно. msg_connect достаточно.
    #
    # Запускаем flowgraph (top block)
    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    tb.flowgraph_started.set()


    # Отправка тестового сообщения через PMT на tx.msg_tx
    # data = b'Hello'
    # msg = pmt.init_u8vector(len(data), data)
    # tx.message_port_pub(pmt.intern('msg_tx'), msg)


    try:
        input('Press Enter to quit: ')
    except EOFError:
        pass

    tb.stop()
    tb.wait()

if __name__ == "__main__":
    main()