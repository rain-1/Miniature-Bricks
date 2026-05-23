#!/usr/bin/env python3
import inkex
import random
from inkex import Group, Rectangle, PathElement

class MiniatureBricks(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--brick_width", type=float, default=10.0)
        pars.add_argument("--brick_height", type=float, default=3.0)
        pars.add_argument("--mortar_gap", type=float, default=0.5)
        pars.add_argument("--imperfection", type=float, default=0.4)
        pars.add_argument("--pattern", type=str, default="running")
        pars.add_argument("--enable_frames", type=inkex.Boolean, default=False)

    def effect(self):
        if not self.svg.selection:
            inkex.errormsg("Please select at least one shape.")
            return

        w = self.options.brick_width
        h = self.options.brick_height
        gap = self.options.mortar_gap
        pattern = self.options.pattern
        enable_frames = self.options.enable_frames
        
        style = {'fill': 'none', 'stroke': '#000000', 'stroke-width': '0.25'}
        nodes = list(self.svg.selection.values())

        if enable_frames and len(nodes) > 1:
            nodes.sort(key=lambda n: n.bounding_box().area if n.bounding_box() else 0, reverse=True)
            wall_node = nodes[0]
            windows = nodes[1:]
            
            bbox = wall_node.bounding_box()
            if not bbox: return
            
            mask = inkex.Mask()
            mask.set('id', self.svg.get_unique_id('wall_mask'))
            mask.set('maskUnits', 'userSpaceOnUse')
            self.svg.defs.append(mask)
            
            wall_bg = wall_node.duplicate()
            wall_bg.style = {'fill': 'white', 'stroke': 'none'}
            mask.append(wall_bg)
            
            brick_group = Group()
            brick_group.set('id', self.svg.get_unique_id('brick_pattern'))
            brick_group.set('mask', f'url(#{mask.get_id()})')
            
            self.generate_brick_grid(brick_group, bbox, w, h, gap, pattern, style)
            
            frame_group = Group()
            frame_group.set('id', self.svg.get_unique_id('window_frames'))
            
            for win in windows:
                win_bbox = win.bounding_box()
                if not win_bbox: continue
                
                black_hole = Rectangle()
                black_hole.set('x', str(win_bbox.left - h))
                black_hole.set('y', str(win_bbox.top - w))
                black_hole.set('width', str(win_bbox.width + 2*h))
                black_hole.set('height', str(win_bbox.height + w + h))
                black_hole.style = {'fill': 'black', 'stroke': 'none'}
                mask.append(black_hole)
                
                self.generate_window_frame(frame_group, win_bbox, w, h, gap, style)
                
            parent = wall_node.getparent()
            parent.insert(parent.index(wall_node) + 1, brick_group)
            parent.insert(parent.index(wall_node) + 2, frame_group)
            
        else:
            for node in nodes:
                bbox = node.bounding_box()
                if not bbox: continue
                
                clip = inkex.ClipPath()
                clip.set('id', self.svg.get_unique_id('wall_clip'))
                self.svg.defs.append(clip)
                
                clip_shape = node.duplicate()
                clip_shape.transform = inkex.Transform()
                clip.append(clip_shape)

                brick_group = Group()
                brick_group.set('id', self.svg.get_unique_id('brick_pattern'))
                brick_group.set('clip-path', f'url(#{clip.get_id()})')
                
                self.generate_brick_grid(brick_group, bbox, w, h, gap, pattern, style)
                
                parent = node.getparent()
                parent.insert(parent.index(node) + 1, brick_group)

    def generate_brick_grid(self, parent, bbox, w, h, gap, pattern, style):
        header_w = max(0.1, (w - gap) / 2.0)
        row_height = h + gap
        num_rows = int(bbox.height / row_height) + 2

        for row in range(num_rows):
            y = bbox.top + (row * row_height)
            
            if pattern == "running":
                x_offset = (row % 2) * ((w + gap) / 2.0)
                x = bbox.left - w + x_offset
                while x < bbox.right:
                    self.add_brick(parent, x, y, w, h, style)
                    x += w + gap

            elif pattern == "flemish":
                start_offset = 0 if row % 2 == 0 else (w - header_w) / 2.0
                x = bbox.left - (w * 2) + start_offset
                is_stretcher = True
                while x < bbox.right:
                    current_w = w if is_stretcher else header_w
                    self.add_brick(parent, x, y, current_w, h, style)
                    x += current_w + gap
                    is_stretcher = not is_stretcher

            elif pattern == "english":
                if row % 2 == 0:
                    x = bbox.left - w
                    while x < bbox.right:
                        self.add_brick(parent, x, y, w, h, style)
                        x += w + gap
                else:
                    offset = (w - header_w) / 2.0
                    x = bbox.left - w + offset
                    while x < bbox.right:
                        self.add_brick(parent, x, y, header_w, h, style)
                        x += header_w + gap

    def generate_window_frame(self, parent, bbox, w, h, gap, style):
        curr_x = bbox.left - h
        while curr_x < bbox.right + h:
            bw = h
            if curr_x + bw > bbox.right + h: bw = (bbox.right + h) - curr_x
            self.add_brick(parent, curr_x, bbox.top - w, bw, w, style)
            curr_x += h + gap
            
        curr_x = bbox.left - h
        while curr_x < bbox.right + h:
            bw = h
            if curr_x + bw > bbox.right + h: bw = (bbox.right + h) - curr_x
            self.add_brick(parent, curr_x, bbox.bottom, bw, h, style)
            curr_x += h + gap
            
        curr_y = bbox.top
        while curr_y < bbox.bottom:
            bh = h
            if curr_y + bh > bbox.bottom: bh = bbox.bottom - curr_y
            self.add_brick(parent, bbox.left - h, curr_y, h, bh, style)
            self.add_brick(parent, bbox.right, curr_y, h, bh, style)
            curr_y += h + gap

    def add_brick(self, parent, x, y, width, height, style):
        imp = self.options.imperfection
        
        # If no weathering is applied, use standard rectangles for file efficiency
        if imp <= 0.001:
            rect = Rectangle()
            rect.set('x', str(x))
            rect.set('y', str(y))
            rect.set('width', str(width))
            rect.set('height', str(height))
            rect.style = style
            parent.append(rect)
            return

        # Cap the maximum imperfection at 40% of the brick's size so it doesn't self-intersect
        max_x_chip = width * 0.4
        max_y_chip = height * 0.4

        # Generate 8 random offsets (2 for each of the 4 corners)
        dx1 = min(random.uniform(0, imp), max_x_chip)
        dy1 = min(random.uniform(0, imp), max_y_chip)
        dx2 = min(random.uniform(0, imp), max_x_chip)
        dy2 = min(random.uniform(0, imp), max_y_chip)
        dx3 = min(random.uniform(0, imp), max_x_chip)
        dy3 = min(random.uniform(0, imp), max_y_chip)
        dx4 = min(random.uniform(0, imp), max_x_chip)
        dy4 = min(random.uniform(0, imp), max_y_chip)

        # Randomly choose if a corner is CHIPPED (Line) or TUMBLED (Quadratic Bezier)
        def corner_cmd(c_x, c_y, e_x, e_y):
            if random.random() > 0.5:
                # Quadratic Bezier: uses the original sharp corner as the control point for a smooth curve
                return f"Q {c_x},{c_y} {e_x},{e_y}"
            else:
                # Straight line: creates a sharp, chipped chamfer cut
                return f"L {e_x},{e_y}"

        # Draw the custom brick path
        path_data = [
            f"M {x+dx1},{y}",                                      # Top-Left start
            f"L {x+width-dx2},{y}",                                # Top edge
            corner_cmd(x+width, y, x+width, y+dy2),                # Top-Right corner
            f"L {x+width},{y+height-dy3}",                         # Right edge
            corner_cmd(x+width, y+height, x+width-dx3, y+height),  # Bottom-Right corner
            f"L {x+dx4},{y+height}",                               # Bottom edge
            corner_cmd(x, y+height, x, y+height-dy4),              # Bottom-Left corner
            f"L {x},{y+dy1}",                                      # Left edge
            corner_cmd(x, y, x+dx1, y),                            # Top-Left corner (closing)
            "Z"
        ]
        
        elem = PathElement()
        elem.set('d', ' '.join(path_data))
        elem.style = style
        parent.append(elem)

if __name__ == '__main__':
    MiniatureBricks().run()