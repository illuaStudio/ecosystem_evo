import pygame
import sys
import traceback


def main():
    print("=== Ecosystem Evolution 起動開始 ===")

    try:
        from src.core.engine import SimulationEngine

        pygame.init()
        engine = SimulationEngine()
        engine.run()

    except Exception:
        print("!!! 重大エラー !!!")
        print(traceback.format_exc())
        input("\nEnterキーを押して終了してください...")
    else:
        print("=== 正常終了 ===")
    finally:
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    main()
