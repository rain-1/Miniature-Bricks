#!/usr/bin/env python3
import inkex
import random
import math
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
            
            original_parent = wall_node.getparent()
            
            if not isinstance(wall_node, inkex.PathElement):
                new_wall_node = wall_node.to_path_element()
                # 2. Swap the old node for the new one in the SVG document
                original_parent.replace(wall_node, new_wall_node)
                wall_node = new_wall_node
                
            wall_node.apply_transform()
            
            # Use 'original_parent' later for inserting your groups
            parent = original_parent 
            
            for i, win in enumerate(windows):
                if not isinstance(win, inkex.PathElement):
                    new_win = win.to_path_element()
                    win.getparent().replace(win, new_win)
                    windows[i] = new_win
                windows[i].apply_transform()
            
            bbox = wall_node.bounding_box()
            if not bbox: return
            
            mask = inkex.Mask()
            mask.set('id', self.svg.get_unique_id('wall_mask'))
            mask.set('maskUnits', 'userSpaceOnUse')
            mask.set('maskContentUnits', 'userSpaceOnUse')
            self.svg.defs.append(mask)
            
            wall_bg = inkex.PathElement()
            wall_bg.path = wall_node.path
            wall_bg.transform = wall_node.transform
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
                
                # Restore the clean, thick blackout mask
                black_hole = inkex.PathElement()
                black_hole.path = win.path
                black_hole.transform = win.transform
                black_hole.style = {
                    'fill': 'black', 
                    'stroke': 'black', 
                    'stroke-width': str(w * 2.1), # Expands outward to perfectly hide wall bricks
                    'stroke-linejoin': 'round'
                }
                mask.append(black_hole)
                
                # Generate the curved path frame
                self.generate_path_frame(frame_group, mask, win, w, h, gap, style)
                
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

    def build_lut_from_node(self, path_node):
        """Converts ANY Inkscape path into a pure mathematical Look-Up Table of coordinates"""
        # Convert the path into a list of cubic bezier curves (works in all Inkscape versions)
        csp = path_node.path.to_superpath()
        lut = []
        total_len = 0.0
        
        for subpath in csp:
            if len(subpath) < 2: continue
            
            sub_points = []
            # Loop through the control points of the bezier curves
            for i in range(len(subpath) - 1):
                p0 = subpath[i][1]
                h1 = subpath[i][2]
                h2 = subpath[i+1][0]
                p1 = subpath[i+1][1]
                
                # Sample 20 points along each segment of the curve
                steps = 20 
                for s in range(steps):
                    t = s / float(steps)
                    mt = 1.0 - t
                    # Standard Cubic Bezier formula
                    x = (mt**3)*p0[0] + 3*(mt**2)*t*h1[0] + 3*mt*(t**2)*h2[0] + (t**3)*p1[0]
                    y = (mt**3)*p0[1] + 3*(mt**2)*t*h1[1] + 3*mt*(t**2)*h2[1] + (t**3)*p1[1]
                    sub_points.append((x, y))
                    
            sub_points.append((subpath[-1][1][0], subpath[-1][1][1]))
            
            if not lut:
                lut.append((0.0, sub_points[0][0], sub_points[0][1]))
                
            last_x, last_y = lut[-1][1], lut[-1][2]
            
            # Map out the exact millimeter distances between all points
            for pt in sub_points[1:]:
                dx = pt[0] - last_x
                dy = pt[1] - last_y
                dist = math.hypot(dx, dy)
                if dist > 0.001: # Avoid duplicate stacking points
                    total_len += dist
                    lut.append((total_len, pt[0], pt[1]))
                    last_x, last_y = pt[0], pt[1]
                    
        return lut, total_len

    def generate_path_frame(self, parent, mask_parent, path_node, w, h, gap, style):
        lut, total_len = self.build_lut_from_node(path_node)
        
        if total_len <= 0 or not lut:
            return
            
        win_bbox = path_node.bounding_box()
        cx, cy = win_bbox.center.x, win_bbox.center.y
        
        def get_lut_point(length):
            length = max(0.0, min(total_len, length))
            for idx in range(len(lut) - 1):
                if lut[idx+1][0] >= length:
                    l1, x1, y1 = lut[idx]
                    l2, x2, y2 = lut[idx+1]
                    if l2 == l1: return x1, y1
                    factor = (length - l1) / (l2 - l1)
                    return x1 + factor * (x2 - x1), y1 + factor * (y2 - y1)
            return lut[-1][1], lut[-1][2]

        # 1. Chunk the path into "Bottom" (flat) vs "Arch/Sides" (soldier) segments
        segments = []
        current_segment = []
        is_current_bottom = None

        for pt in lut:
            l, px, py = pt
            # A point is on the "bottom" if it's within 1mm of the lowest point of the shape
            on_bottom = abs(py - win_bbox.bottom) <= 1.0

            if is_current_bottom is None:
                is_current_bottom = on_bottom

            if on_bottom == is_current_bottom:
                current_segment.append(pt)
            else:
                segments.append({'is_bottom': is_current_bottom, 'pts': current_segment})
                current_segment = [pt]
                is_current_bottom = on_bottom

        if current_segment:
            segments.append({'is_bottom': is_current_bottom, 'pts': current_segment})

        # 2. Iterate through each architectural segment
        for seg in segments:
            if len(seg['pts']) < 2: continue
            
            seg_start_l = seg['pts'][0][0]
            seg_end_l = seg['pts'][-1][0]
            seg_len = seg_end_l - seg_start_l
            
            if seg_len <= 0.1: continue
            
            if seg['is_bottom']:
                # Bottom threshold/sill: Bricks lay flat (length w, thickness h)
                num_bricks = max(1, int(round(seg_len / (w + gap))))
                step = seg_len / num_bricks
                bh_actual = h
            else:
                # Arches and jambs: Bricks stand radially (length h, thickness w)
                num_bricks = max(1, int(round(seg_len / (h + gap))))
                step = seg_len / num_bricks
                bh_actual = w
                
            bw_actual = step - gap
            
            for i in range(num_bricks):
                l = seg_start_l + i * step + step / 2.0
                
                # Check tangent trajectory
                x1, y1 = get_lut_point(max(0.0, l - 1.0))
                x2, y2 = get_lut_point(min(total_len, l + 1.0))
                cx_brick, cy_brick = get_lut_point(l)
                
                dx = x2 - x1
                dy = y2 - y1
                mag = math.hypot(dx, dy)
                if mag == 0: tx, ty = 1, 0
                else: tx, ty = dx/mag, dy/mag
                    
                nx, ny = -ty, tx
                
                # Normal must point outward away from the center cutout
                vx, vy = cx_brick - cx, cy_brick - cy
                if (nx * vx + ny * vy) < 0:
                    nx, ny = -nx, -ny
                    
                c_x = cx_brick + nx * (bh_actual / 2.0)
                c_y = cy_brick + ny * (bh_actual / 2.0)
                
                angle_deg = math.degrees(math.atan2(ty, tx))
                transform = f"translate({c_x}, {c_y}) rotate({angle_deg})"
                
                # Draw the visible weathered brick
                self.add_brick(parent, -bw_actual/2, -bh_actual/2, bw_actual, bh_actual, style, transform=transform)

                # Draw the Conformal Blackout Mask Block
                # We make it slightly larger (+0.5mm) to perfectly cover mortar gaps
                rect = Rectangle()
                rect.set('x', str(-(step + 0.5)/2))
                rect.set('y', str(-(bh_actual + 0.5)/2))
                rect.set('width', str(step + 0.5))
                rect.set('height', str(bh_actual + 0.5))
                rect.style = {'fill': 'black', 'stroke': 'none'}
                rect.set('transform', transform)
                mask_parent.append(rect)


    def add_brick(self, parent, x, y, width, height, style, transform=None):
        imp = self.options.imperfection
        
        if imp <= 0.001:
            rect = Rectangle()
            rect.set('x', str(x))
            rect.set('y', str(y))
            rect.set('width', str(width))
            rect.set('height', str(height))
            rect.style = style
            if transform: rect.set('transform', transform)
            parent.append(rect)
            return

        max_x_chip = width * 0.4
        max_y_chip = height * 0.4

        dx1 = min(random.uniform(0, imp), max_x_chip)
        dy1 = min(random.uniform(0, imp), max_y_chip)
        dx2 = min(random.uniform(0, imp), max_x_chip)
        dy2 = min(random.uniform(0, imp), max_y_chip)
        dx3 = min(random.uniform(0, imp), max_x_chip)
        dy3 = min(random.uniform(0, imp), max_y_chip)
        dx4 = min(random.uniform(0, imp), max_x_chip)
        dy4 = min(random.uniform(0, imp), max_y_chip)

        def corner_cmd(c_x, c_y, e_x, e_y):
            if random.random() > 0.5:
                return f"Q {c_x},{c_y} {e_x},{e_y}"
            else:
                return f"L {e_x},{e_y}"

        path_data = [
            f"M {x+dx1},{y}",
            f"L {x+width-dx2},{y}",
            corner_cmd(x+width, y, x+width, y+dy2),
            f"L {x+width},{y+height-dy3}",
            corner_cmd(x+width, y+height, x+width-dx3, y+height),
            f"L {x+dx4},{y+height}",
            corner_cmd(x, y+height, x, y+height-dy4),
            f"L {x},{y+dy1}",
            corner_cmd(x, y, x+dx1, y),
            "Z"
        ]
        
        elem = PathElement()
        elem.set('d', ' '.join(path_data))
        elem.style = style
        if transform: elem.set('transform', transform)
        parent.append(elem)

if __name__ == '__main__':
    MiniatureBricks().run()