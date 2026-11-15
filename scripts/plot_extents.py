import matplotlib.pyplot as plt
import matplotlib.patches as patches

# boxes in lon/lat deg
sim = (76.8, 77.8, 17.7, 18.7)  # W E S N
msr = (77.0578, 77.3808, 18.1357, 18.5881)
ellipse = (77.3545025, 77.5052272, 18.3987795, 18.5337996)

fig, ax = plt.subplots(figsize=(8, 8))
ax.add_patch(patches.Rectangle((sim[0], sim[2]), sim[1]-sim[0], sim[3]-sim[2],
             facecolor='#fde9c8', edgecolor='black', linewidth=1.5, label='SIM3464 Jezero+Nili Planum 1x1deg'))
ax.add_patch(patches.Rectangle((msr[0], msr[2]), msr[1]-msr[0], msr[3]-msr[2],
             facecolor='#a6cee3', edgecolor='blue', linewidth=1.5, label='MSR TRN HiRISE soc_003 mosaic'))
ax.add_patch(patches.Rectangle((ellipse[0], ellipse[2]), ellipse[1]-ellipse[0], ellipse[3]-ellipse[2],
             facecolor='none', edgecolor='red', linewidth=1.5, label='SIM3464 LandingEllipse (W Jezero floor)'))
ax.set_xlim(76.7, 77.9); ax.set_ylim(17.6, 18.8)
ax.set_xlabel('East longitude (deg)'); ax.set_ylabel('North latitude (deg)')
ax.set_title('SIM3464 vs MSR TRN HiRISE soc_003 extents (lon/lat, Mars 2000 sphere)')
ax.legend(fontsize=8, loc='lower right')
ax.set_aspect('equal', adjustable='box')
plt.tight_layout(); plt.savefig('sim_vs_msr_extents.png', dpi=150)
print('saved sim_vs_msr_extents.png')
