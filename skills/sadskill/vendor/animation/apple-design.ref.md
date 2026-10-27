# Reference: Apple-Style Interface & Motion Design

Origin: Animation & Motion Community  
License: MIT  

## Physical Motion Principles

1. **Springs Over Linear Easing**:
   - Natural physics governs real-world movement. Use spring curves (stiffness: 300, damping: 30) rather than mechanical linear transitions.
2. **Interruptibility**:
   - Animations must be interruptible. If a user swipes or clicks while an element is mid-transition, the element must smoothly adopt the new trajectory without jumping or snapping.
3. **Spatial Consistency**:
   - Elements must originate from and return to recognizable spatial anchors (e.g. a sheet expands from the clicked button and collapses back into it).
4. **Materials & Depth**:
   - Use translucent materials (`backdrop-filter: blur(20px)`) with subtle hairline specular borders to simulate layered glass surfaces.
