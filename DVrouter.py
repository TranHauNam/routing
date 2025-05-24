####################################################
# DVrouter.py
# Name: Doan Van Giap, Tran Hau Nam
# HUID:
#####################################################

from router import Router
from packet import Packet
import json

INFINITY = 16  # Như gợi ý trong README


class DVrouter(Router):
    """Distance vector routing protocol implementation."""

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)
        self.heartbeat_time = heartbeat_time
        self.last_time = 0

        # --- Cấu trúc dữ liệu Distance-Vector ---
        self.distance_vector = {self.addr: (0, self.addr)}  # {dest: (cost, next_hop)}
        self.neighbors = {}  # {neighbor_addr: {'port': port, 'cost': cost}}
        self.neighbor_dvs = {}  # {neighbor_addr: {dest: cost}}

    def handle_packet(self, port, packet):
        """Process incoming packet."""
        if packet.is_traceroute:
            # Gói traceroute (dữ liệu)
            if packet.dst_addr in self.distance_vector:
                cost, next_hop = self.distance_vector[packet.dst_addr]
                if cost < INFINITY and next_hop is not None and next_hop in self.neighbors:
                    next_port = self.neighbors[next_hop]['port']
                    self.send(next_port, packet)
            # Nếu không có đường đi, gói tin sẽ bị loại bỏ
        else:
            # Gói định tuyến (Distance Vector)
            try:
                received_dv = json.loads(packet.content)
                src_addr = packet.src_addr

                # Chỉ xử lý nếu láng giềng còn tồn tại
                if src_addr in self.neighbors:
                    self.neighbor_dvs[src_addr] = received_dv
                    self.update_dv()

            except (json.JSONDecodeError, KeyError):
                print(f"{self.addr}: Received malformed DV packet.")

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link."""
        # print(f"{self.addr}: New link to {endpoint} on port {port} with cost {cost}")
        self.neighbors[endpoint] = {'port': port, 'cost': cost}
        self.neighbor_dvs[endpoint] = {}  # Khởi tạo DV trống cho láng giềng mới
        self.update_dv()  # Cập nhật và phát sóng

    def handle_remove_link(self, port):
        """Handle removed link."""
        endpoint_to_remove = None
        for addr, info in self.neighbors.items():
            if info['port'] == port:
                endpoint_to_remove = addr
                break

        if endpoint_to_remove:
            # print(f"{self.addr}: Link to {endpoint_to_remove} on port {port} removed.")
            del self.neighbors[endpoint_to_remove]
            if endpoint_to_remove in self.neighbor_dvs:
                del self.neighbor_dvs[endpoint_to_remove]

            # Đặt tất cả các đường đi qua láng giềng bị loại bỏ thành INFINITY
            changed = False
            for dest, (cost, next_hop) in list(self.distance_vector.items()):
                if next_hop == endpoint_to_remove:
                    self.distance_vector[dest] = (INFINITY, None)
                    changed = True

            # Tính toán lại và phát sóng nếu cần
            self.update_dv()

    def handle_time(self, time_ms):
        """Handle current time."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            # Gửi DV định kỳ
            self.broadcast_dv()

    def update_dv(self):
        """Updates this router's distance vector using Bellman-Ford."""
        old_dv = self.distance_vector.copy()
        changed = False

        # Thu thập tất cả các đích có thể có
        all_dests = set([self.addr])
        all_dests.update(self.neighbors.keys())
        for dv in self.neighbor_dvs.values():
            all_dests.update(dv.keys())

        new_dv = {}
        new_dv[self.addr] = (0, self.addr)  # Luôn biết đường về chính mình

        for dest in all_dests:
            if dest == self.addr:
                continue

            min_cost = INFINITY
            next_hop = None

            # Tính toán chi phí qua từng láng giềng v
            for v_addr, v_info in self.neighbors.items():
                cost_xv = v_info['cost']  # c(x,v)

                # Lấy D_v(y)
                if dest == v_addr:
                    cost_vy = 0  # D_v(v) = 0
                else:
                    cost_vy = self.neighbor_dvs.get(v_addr, {}).get(dest, INFINITY)

                total_cost = cost_xv + cost_vy

                # Cập nhật nếu chi phí tốt hơn
                if total_cost < min_cost:
                    min_cost = total_cost
                    next_hop = v_addr

            min_cost = min(min_cost, INFINITY)  # Giới hạn chi phí

            # Chỉ thêm vào DV nếu có thể đến được
            if min_cost < INFINITY:
                new_dv[dest] = (min_cost, next_hop)

        # Kiểm tra xem DV có thay đổi không
        if new_dv != self.distance_vector:
            changed = True
            self.distance_vector = new_dv

        # Nếu có thay đổi, phát sóng
        if changed:
            # print(f"{self.addr} DV updated: {self.get_dv_for_broadcast()}") # Debug
            self.broadcast_dv()

    def get_dv_for_broadcast(self):
        """Returns a simple {dest: cost} dictionary for broadcasting."""
        return {dest: cost for dest, (cost, _) in self.distance_vector.items()}

    def broadcast_dv(self):
        """Broadcasts this router's DV to all neighbors, implementing poisoned reverse."""
        full_dv = self.get_dv_for_broadcast()

        for neighbor_addr, neighbor_info in self.neighbors.items():
            dv_to_send = full_dv.copy()

            # Poisoned Reverse:
            for dest, (cost, next_hop) in self.distance_vector.items():
                if next_hop == neighbor_addr and dest != neighbor_addr:
                    dv_to_send[dest] = INFINITY

            packet_content = json.dumps(dv_to_send)
            dv_packet = Packet(Packet.ROUTING, self.addr, neighbor_addr, packet_content)
            self.send(neighbor_info['port'], dv_packet)

    def __repr__(self):
        """Representation for debugging in the network visualizer."""
        # TODO
        #   NOTE This method is for your own convenience and will not be graded
        return f"DVrouter(addr={self.addr})"