import pygame
import sys
import traceback

print("=== Ecosystem Evolution 起動開始 ===")

try:
    from engine import SimulationEngine

    pygame.init()
    engine = SimulationEngine()
    engine.run()

except Exception as e:
    print("!!! 重大エラー !!!")
    print(traceback.format_exc())
    input("\nEnterキーを押して終了してください...")

print("=== 正常終了 ===")
pygame.quit()
sys.exit()