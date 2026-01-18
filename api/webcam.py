import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import cv2
import threading
import time
import numpy as np
from mediapipe import solutions

class EyeTracker:
    def __init__(self):
        self.cap = None
        self.is_running = False
        self.paused = False  # <--- NEW: Pause flag
        self.is_distracted = False
        self.distraction_reason = ""
        self.current_frame = None

        mp_face_mesh = solutions.face_mesh
        self.mp_drawing = solutions.drawing_utils
        self.mp_drawing_styles = solutions.drawing_styles

        self.face_mesh = mp_face_mesh.FaceMesh(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            refine_landmarks=True
        )

    def start(self):
        self.is_running = True
        self.paused = False
        self.thread = threading.Thread(target=self._run_loop)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.is_running = False
        if self.cap:
            self.cap.release()

    def set_paused(self, state):
        """Pauses camera access to free up resources for Audio"""
        self.paused = state

    def get_frame(self):
        return self.current_frame

    def _run_loop(self):
        self.cap = cv2.VideoCapture(0)
        cam_matrix = None
        dist_matrix = np.zeros((4, 1), dtype=np.float64)

        while self.is_running:
            # --- PAUSE LOGIC ---
            if self.paused:
                # Sleep to save CPU while microphone is using resources
                time.sleep(0.5) 
                continue
            # -------------------

            if not self.cap.isOpened():
                self.cap.open(0) # Re-open if it was lost
                time.sleep(0.1)
                continue

            success, image = self.cap.read()
            if not success:
                time.sleep(0.1)
                continue

            image = cv2.flip(image, 1)
            img_h, img_w, _ = image.shape

            if self.face_mesh:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                image_rgb.flags.writeable = False
                results = self.face_mesh.process(image_rgb)
                image_rgb.flags.writeable = True

                if results.multi_face_landmarks:
                    for face_landmarks in results.multi_face_landmarks:
                        
                        # Draw Mesh
                        self.mp_drawing.draw_landmarks(
                            image=image,
                            landmark_list=face_landmarks,
                            connections=solutions.face_mesh.FACEMESH_TESSELATION,
                            landmark_drawing_spec=None,
                            connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_tesselation_style()
                        )
                        self.mp_drawing.draw_landmarks(
                            image=image,
                            landmark_list=face_landmarks,
                            connections=solutions.face_mesh.FACEMESH_CONTOURS,
                            landmark_drawing_spec=None,
                            connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_contours_style()
                        )

                        # Math Logic
                        face_3d = []
                        face_2d = []

                        for idx, lm in enumerate(face_landmarks.landmark):
                            if idx in [1, 199, 33, 263, 61, 291]:
                                x, y = int(lm.x * img_w), int(lm.y * img_h)
                                face_2d.append([x, y])
                                face_3d.append([x, y, lm.z])

                        face_2d = np.array(face_2d, dtype=np.float64)
                        face_3d = np.array(face_3d, dtype=np.float64)

                        if cam_matrix is None:
                            focal_length = 1 * img_w
                            cam_matrix = np.array([[focal_length, 0, img_h / 2],
                                                   [0, focal_length, img_w / 2],
                                                   [0, 0, 1]])

                        success, rot_vec, trans_vec = cv2.solvePnP(face_3d, face_2d, cam_matrix, dist_matrix)

                        if success:
                            rmat, jac = cv2.Rodrigues(rot_vec)
                            data = cv2.RQDecomp3x3(rmat)
                            angles = data[0]
                            x_angle = angles[0] * 360
                            y_angle = angles[1] * 360

                            if y_angle < -20:
                                self.is_distracted = True
                                self.distraction_reason = "Stop looking to the left!"
                            elif y_angle > 20:
                                self.is_distracted = True
                                self.distraction_reason = "Stop looking to the right"
                            elif x_angle < -25:
                                self.is_distracted = True
                                self.distraction_reason = "Stop looking down!"
                            elif x_angle > 25:
                                self.is_distracted = True
                                self.distraction_reason = "Stop looking up!"
                            else:
                                self.is_distracted = False
                                self.distraction_reason = ""
                else:
                    self.is_distracted = True
                    self.distraction_reason = "Away from Desk"

            self.current_frame = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            time.sleep(0.06)

        self.cap.release()