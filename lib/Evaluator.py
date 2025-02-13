###########################################################################################
#                                                                                         #
# Evaluator class: Implements the most popular metrics for object detection               #
#                                                                                         #
# Developed by: Rafael Padilla (rafael.padilla@smt.ufrj.br)                               #
#        SMT - Signal Multimedia and Telecommunications Lab                               #
#        COPPE - Universidade Federal do Rio de Janeiro                                   #
#        Last modification: Oct 9th 2018                                                 #
###########################################################################################

import os
import sys
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np

from BoundingBox import *
from BoundingBoxes import *
from utils import *


class Evaluator:
    def GetPascalVOCMetrics(self,
                            boundingboxes,
                            IOUThreshold=0.5,
                            method=MethodAveragePrecision.EveryPointInterpolation):
        """Get the metrics used by the VOC Pascal 2012 challenge.
        Get
        Args:
            boundingboxes: Object of the class BoundingBoxes representing ground truth and detected
            bounding boxes;
            IOUThreshold: IOU threshold indicating which detections will be considered TP or FP
            (default value = 0.5);
            method (default = EveryPointInterpolation): It can be calculated as the implementation
            in the official PASCAL VOC toolkit (EveryPointInterpolation), or applying the 11-point
            interpolatio as described in the paper "The PASCAL Visual Object Classes(VOC) Challenge"
            or EveryPointInterpolation"  (ElevenPointInterpolation);
        Returns:
            A list of dictionaries. Each dictionary contains information and metrics of each class.
            The keys of each dictionary are:
            dict['class']: class representing the current dictionary;
            dict['precision']: array with the precision values;
            dict['recall']: array with the recall values;
            dict['AP']: average precision;
            dict['interpolated precision']: interpolated precision values;
            dict['interpolated recall']: interpolated recall values;
            dict['total positives']: total number of ground truth positives;
            dict['total TP']: total number of True Positive detections;
            dict['total FP']: total number of False Positive detections;
        """
        ret = [
        ]  # list containing metrics (precision, recall, average precision) of each class
        # List with all ground truths (Ex: [imageName,class,confidence=1, (bb coordinates XYX2Y2)])
        groundTruths = []
        # List with all detections (Ex: [imageName,class,confidence,(bb coordinates XYX2Y2)])
        detections = []
        # Get all classes
        classes = []
        # Loop through all bounding boxes and separate them into GTs and detections
        for bb in boundingboxes.getBoundingBoxes():
            # [imageName, class, confidence, (bb coordinates XYX2Y2)]
            if bb.getBBType() == BBType.GroundTruth:
                groundTruths.append([
                    bb.getImageName(),
                    bb.getClassId(), 1,
                    bb.getAbsoluteBoundingBox(BBFormat.XYX2Y2)
                ])
            else:
                detections.append([
                    bb.getImageName(),
                    bb.getClassId(),
                    bb.getConfidence(),
                    bb.getAbsoluteBoundingBox(BBFormat.XYX2Y2)
                ])
            # get class
            if bb.getClassId() not in classes:
                classes.append(bb.getClassId())
        classes = sorted(classes)
        # Precision x Recall is obtained individually by each class
        # Loop through by classes
        for c in classes:
            # Get only detection of class c
            dects = []
            [dects.append(d) for d in detections if d[1] == c]
            # Get only ground truths of class c, use filename as key
            gts = {}
            npos = 0
            for g in groundTruths:
                if g[1] == c:
                    npos += 1
                    gts[g[0]] = gts.get(g[0], []) + [g]

            # sort detections by decreasing confidence
            dects = sorted(dects, key=lambda conf: conf[2], reverse=True)
            TP = np.zeros(len(dects))
            FP = np.zeros(len(dects))
            # create dictionary with amount of gts for each image
            det = {key: np.zeros(len(gts[key])) for key in gts}

            # print("Evaluating class: %s (%d detections)" % (str(c), len(dects)))
            # Loop through detections
            for d in range(len(dects)):
                # print('dect %s => %s' % (dects[d][0], dects[d][3],))
                # Find ground truth image
                gt = gts[dects[d][0]] if dects[d][0] in gts else []
                iouMax = sys.float_info.min
                for j in range(len(gt)):
                    # print('Ground truth gt => %s' % (gt[j][3],))
                    iou = Evaluator.iou(dects[d][3], gt[j][3])
                    if iou > iouMax:
                        iouMax = iou
                        jmax = j
                # Assign detection as true positive/don't care/false positive
                if iouMax >= IOUThreshold:
                    if det[dects[d][0]][jmax] == 0:
                        TP[d] = 1  # count as true positive
                        det[dects[d][0]][jmax] = 1  # flag as already 'seen'
                        # print("TP")
                    else:
                        FP[d] = 1  # count as false positive
                        # print("FP")
                # - A detected "cat" is overlaped with a GT "cat" with IOU >= IOUThreshold.
                else:
                    FP[d] = 1  # count as false positive
                    # print("FP")
            # compute precision, recall and average precision
            acc_FP = np.cumsum(FP)
            acc_TP = np.cumsum(TP)
            rec = acc_TP / npos
            prec = np.divide(acc_TP, (acc_FP + acc_TP))
            # Depending on the method, call the right implementation
            if method == MethodAveragePrecision.EveryPointInterpolation:
                [ap, mpre, mrec, ii] = Evaluator.CalculateAveragePrecision(
                    rec, prec)
            else:
                [ap, mpre, mrec, _] = Evaluator.ElevenPointInterpolatedAP(
                    rec, prec)
            # add class result in the dictionary to be returned
            r = {
                'class': c,
                'precision': prec,
                'recall': rec,
                'AP': ap,
                'interpolated precision': mpre,
                'interpolated recall': mrec,
                'total positives': npos,
                'total TP': np.sum(TP),
                'total FP': np.sum(FP)
            }
            ret.append(r)
        return ret

    def PlotPrecisionRecallCurve(self,
                                 boundingBoxes,
                                 IOUThreshold=0.5,
                                 method=MethodAveragePrecision.EveryPointInterpolation,
                                 showAP=False,
                                 showInterpolatedPrecision=False,
                                 savePath=None,
                                 showGraphic=True):
        """PlotPrecisionRecallCurve
        Plot the Precision x Recall curve for a given class.
        Args:
            boundingBoxes: Object of the class BoundingBoxes representing ground truth and detected
            bounding boxes;
            IOUThreshold (optional): IOU threshold indicating which detections will be considered
            TP or FP (default value = 0.5);
            method (default = EveryPointInterpolation): It can be calculated as the implementation
            in the official PASCAL VOC toolkit (EveryPointInterpolation), or applying the 11-point
            interpolatio as described in the paper "The PASCAL Visual Object Classes(VOC) Challenge"
            or EveryPointInterpolation"  (ElevenPointInterpolation).
            showAP (optional): if True, the average precision value will be shown in the title of
            the graph (default = False);
            showInterpolatedPrecision (optional): if True, it will show in the plot the interpolated
             precision (default = False);
            savePath (optional): if informed, the plot will be saved as an image in this path
            (ex: /home/mywork/ap.png) (default = None);
            showGraphic (optional): if True, the plot will be shown (default = True)
        Returns:
            A list of dictionaries. Each dictionary contains information and metrics of each class.
            The keys of each dictionary are:
            dict['class']: class representing the current dictionary;
            dict['precision']: array with the precision values;
            dict['recall']: array with the recall values;
            dict['AP']: average precision;
            dict['interpolated precision']: interpolated precision values;
            dict['interpolated recall']: interpolated recall values;
            dict['total positives']: total number of ground truth positives;
            dict['total TP']: total number of True Positive detections;
            dict['total FP']: total number of False Negative detections;
        """
        results = self.GetPascalVOCMetrics(boundingBoxes, IOUThreshold, method)
        result = None
        # Each resut represents a class
        for result in results:
            if result is None:
                raise IOError('Error: Class %d could not be found.' % classId)

            classId = result['class']
            precision = result['precision']
            recall = result['recall']
            average_precision = result['AP']
            mpre = result['interpolated precision']
            mrec = result['interpolated recall']
            npos = result['total positives']
            total_tp = result['total TP']
            total_fp = result['total FP']

            plt.close()
            if showInterpolatedPrecision:
                if method == MethodAveragePrecision.EveryPointInterpolation:
                    plt.plot(mrec, mpre, '--r',
                             label='Interpolated precision (every point)')
                elif method == MethodAveragePrecision.ElevenPointInterpolation:
                    # Uncomment the line below if you want to plot the area
                    # plt.plot(mrec, mpre, 'or', label='11-point interpolated precision')
                    # Remove duplicates, getting only the highest precision of each recall value
                    nrec = []
                    nprec = []
                    for idx in range(len(mrec)):
                        r = mrec[idx]
                        if r not in nrec:
                            idxEq = np.argwhere(mrec == r)
                            nrec.append(r)
                            nprec.append(max([mpre[int(id)] for id in idxEq]))
                    plt.plot(nrec, nprec, 'or',
                             label='11-point interpolated precision')
            plt.plot(recall, precision, label='Precision')
            plt.xlabel('recall')
            plt.ylabel('precision')
            if showAP:
                ap_str = "{0:.2f}%".format(average_precision * 100)
                # ap_str = "{0:.4f}%".format(average_precision * 100)
                plt.title('Precision x Recall curve \nClass: %s, AP: %s' %
                          (str(classId), ap_str))
            else:
                plt.title('Precision x Recall curve \nClass: %s' %
                          str(classId))
            plt.legend(shadow=True)
            plt.grid()
            ############################################################
            # Uncomment the following block to create plot with points #
            ############################################################
            # plt.plot(recall, precision, 'bo')
            # labels = ['R', 'Y', 'J', 'A', 'U', 'C', 'M', 'F', 'D', 'B', 'H', 'P', 'E', 'X', 'N', 'T',
            # 'K', 'Q', 'V', 'I', 'L', 'S', 'G', 'O']
            # dicPosition = {}
            # dicPosition['left_zero'] = (-30,0)
            # dicPosition['left_zero_slight'] = (-30,-10)
            # dicPosition['right_zero'] = (30,0)
            # dicPosition['left_up'] = (-30,20)
            # dicPosition['left_down'] = (-30,-25)
            # dicPosition['right_up'] = (20,20)
            # dicPosition['right_down'] = (20,-20)
            # dicPosition['up_zero'] = (0,30)
            # dicPosition['up_right'] = (0,30)
            # dicPosition['left_zero_long'] = (-60,-2)
            # dicPosition['down_zero'] = (-2,-30)
            # vecPositions = [
            #     dicPosition['left_down'],
            #     dicPosition['left_zero'],
            #     dicPosition['right_zero'],
            #     dicPosition['right_zero'],  #'R', 'Y', 'J', 'A',
            #     dicPosition['left_up'],
            #     dicPosition['left_up'],
            #     dicPosition['right_up'],
            #     dicPosition['left_up'],  # 'U', 'C', 'M', 'F',
            #     dicPosition['left_zero'],
            #     dicPosition['right_up'],
            #     dicPosition['right_down'],
            #     dicPosition['down_zero'],  #'D', 'B', 'H', 'P'
            #     dicPosition['left_up'],
            #     dicPosition['up_zero'],
            #     dicPosition['right_up'],
            #     dicPosition['left_up'],  # 'E', 'X', 'N', 'T',
            #     dicPosition['left_zero'],
            #     dicPosition['right_zero'],
            #     dicPosition['left_zero_long'],
            #     dicPosition['left_zero_slight'],  # 'K', 'Q', 'V', 'I',
            #     dicPosition['right_down'],
            #     dicPosition['left_down'],
            #     dicPosition['right_up'],
            #     dicPosition['down_zero']
            # ]  # 'L', 'S', 'G', 'O'
            # for idx in range(len(labels)):
            #     box = dict(boxstyle='round,pad=.5',facecolor='yellow',alpha=0.5)
            #     plt.annotate(labels[idx],
            #                 xy=(recall[idx],precision[idx]), xycoords='data',
            #                 xytext=vecPositions[idx], textcoords='offset points',
            #                 arrowprops=dict(arrowstyle="->", connectionstyle="arc3"),
            #                 bbox=box)
            if savePath is not None:
                plt.savefig(os.path.join(savePath, classId + '.png'))
            if showGraphic is True:
                plt.show()
                # plt.waitforbuttonpress()
                plt.pause(0.05)
        return results

    @staticmethod
    def CalculateAveragePrecision(rec, prec):
        mrec = []
        mrec.append(0)
        [mrec.append(e) for e in rec]
        mrec.append(1)
        mpre = []
        mpre.append(0)
        [mpre.append(e) for e in prec]
        mpre.append(0)
        for i in range(len(mpre) - 1, 0, -1):
            mpre[i - 1] = max(mpre[i - 1], mpre[i])
        ii = []
        for i in range(len(mrec) - 1):
            if mrec[1+i] != mrec[i]:
                ii.append(i + 1)
        ap = 0
        for i in ii:
            ap = ap + np.sum((mrec[i] - mrec[i - 1]) * mpre[i])
        # return [ap, mpre[1:len(mpre)-1], mrec[1:len(mpre)-1], ii]
        return [ap, mpre[0:len(mpre) - 1], mrec[0:len(mpre) - 1], ii]

    @staticmethod
    # 11-point interpolated average precision
    def ElevenPointInterpolatedAP(rec, prec):
        # def CalculateAveragePrecision2(rec, prec):
        mrec = []
        # mrec.append(0)
        [mrec.append(e) for e in rec]
        # mrec.append(1)
        mpre = []
        # mpre.append(0)
        [mpre.append(e) for e in prec]
        # mpre.append(0)
        recallValues = np.linspace(0, 1, 11)
        recallValues = list(recallValues[::-1])
        rhoInterp = []
        recallValid = []
        # For each recallValues (0, 0.1, 0.2, ... , 1)
        for r in recallValues:
            # Obtain all recall values higher or equal than r
            argGreaterRecalls = np.argwhere(mrec[:] >= r)
            pmax = 0
            # If there are recalls above r
            if argGreaterRecalls.size != 0:
                pmax = max(mpre[argGreaterRecalls.min():])
            recallValid.append(r)
            rhoInterp.append(pmax)
        # By definition AP = sum(max(precision whose recall is above r))/11
        ap = sum(rhoInterp) / 11
        # Generating values for the plot
        rvals = []
        rvals.append(recallValid[0])
        [rvals.append(e) for e in recallValid]
        rvals.append(0)
        pvals = []
        pvals.append(0)
        [pvals.append(e) for e in rhoInterp]
        pvals.append(0)
        # rhoInterp = rhoInterp[::-1]
        cc = []
        for i in range(len(rvals)):
            p = (rvals[i], pvals[i - 1])
            if p not in cc:
                cc.append(p)
            p = (rvals[i], pvals[i])
            if p not in cc:
                cc.append(p)
        recallValues = [i[0] for i in cc]
        rhoInterp = [i[1] for i in cc]
        return [ap, rhoInterp, recallValues, None]

    # For each detections, calculate IOU with reference
    @staticmethod
    def _getAllIOUs(reference, detections):
        ret = []
        bbReference = reference.getAbsoluteBoundingBox(BBFormat.XYX2Y2)
        # img = np.zeros((200,200,3), np.uint8)
        for d in detections:
            bb = d.getAbsoluteBoundingBox(BBFormat.XYX2Y2)
            iou = Evaluator.iou(bbReference, bb)
            # Show blank image with the bounding boxes
            # img = add_bb_into_image(img, d, color=(255,0,0), thickness=2, label=None)
            # img = add_bb_into_image(img, reference, color=(0,255,0), thickness=2, label=None)
            ret.append((iou, reference, d))  # iou, reference, detection
        # cv2.imshow("comparing",img)
        # cv2.waitKey(0)
        # cv2.destroyWindow("comparing")
        # sort by iou (from highest to lowest)
        return sorted(ret, key=lambda i: i[0], reverse=True)

    @staticmethod
    def iou(boxA, boxB):
        # if boxes dont intersect
        if Evaluator._boxesIntersect(boxA, boxB) is False:
            return 0
        interArea = Evaluator._getIntersectionArea(boxA, boxB)
        union = Evaluator._getUnionAreas(boxA, boxB, interArea=interArea)
        # intersection over union
        iou = interArea / union
        assert iou >= 0
        return iou

    # boxA = (Ax1,Ay1,Ax2,Ay2)
    # boxB = (Bx1,By1,Bx2,By2)
    @staticmethod
    def _boxesIntersect(boxA, boxB):
        if boxA[0] > boxB[2]:
            return False  # boxA is right of boxB
        if boxB[0] > boxA[2]:
            return False  # boxA is left of boxB
        if boxA[3] < boxB[1]:
            return False  # boxA is above boxB
        if boxA[1] > boxB[3]:
            return False  # boxA is below boxB
        return True

    @staticmethod
    def _getIntersectionArea(boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        # intersection area
        return (xB - xA + 1) * (yB - yA + 1)

    @staticmethod
    def _getUnionAreas(boxA, boxB, interArea=None):
        area_A = Evaluator._getArea(boxA)
        area_B = Evaluator._getArea(boxB)
        if interArea is None:
            interArea = Evaluator._getIntersectionArea(boxA, boxB)
        return float(area_A + area_B - interArea)

    @staticmethod
    def _getArea(box):
        return (box[2] - box[0] + 1) * (box[3] - box[1] + 1)

    def GetRelativeMetrics_F1(self, boundingboxes, confidence_gt=0.20, confidence_det=0.20, iou_threshold=0.5):
        '''
        Output: The performance F1 metrics relative to the ground truth obtained through a highly accurate model.
        '''
        def _evaluate(bb_image_gt, bb_image_det):
            # Note: The simple logic to compute relative performance
            # is borrowed from the DDS paper.
            tp_list = []
            fp_list = []
            fn_list = []
            count_list = []
            stats_per_image = {}
            for imageName in bb_image_gt:
                bb_gts = bb_image_gt[imageName]
                bb_dets = bb_image_det[imageName]
                tp = 0
                fp = 0
                fn = 0
                count = 0
                for bb_det in bb_dets:
                    found = False
                    for bb_gt in bb_gts:
                        if Evaluator.iou(bb_gt[2], bb_det[2]) >= iou_threshold:
                            found = True
                            break
                    if found:
                        tp += 1
                    else:
                        fp += 1

                for bb_gt in bb_gts:
                    found = False
                    for bb_det in bb_dets:
                        if Evaluator.iou(bb_gt[2], bb_det[2]) >= iou_threshold:
                            found = True
                            break
                    if not found:
                        fn += 1
                    # else:
                    count += 1
                tp_list.append(tp)
                fp_list.append(fp)
                fn_list.append(fn)
                count_list.append(count)
                stats_per_image[imageName] = [tp, fp, fn]

            # for imageName, stats in stats_per_image.items():
            #    print("Stats: ", imageName, stats)

            tp = sum(tp_list)
            fp = sum(fp_list)
            fn = sum(fn_list)
            count = sum(count_list)
            precision = round(tp/(tp+fp), 3)
            recall = round(tp/(tp+fn), 3)
            f1 = round((2.0*tp/(2.0*tp+fp+fn)), 3)

            return tp, fp, fn, count, precision, recall, f1

        # Seperate bounding boxes per image (frame)
        bb_image_gt = {}
        bb_image_det = {}
        # Check the class categories and labels here.
        # https://tech.amikelive.com/node-718/what-object-categories-labels-are-in-coco-dataset/
        # [car, bus, train, truck]. This is for DDS trafic videos
        classes = ['3', '6', '4', '8']

        # [person, chair, dining table]. This is for PKUMMD dataset videos
        # classes = ['1', '62', '67']
        # classes = {
        #     "vehicle": [3, 6, 7, 8], # [car, bus, train, truck]
        #     "persons": [1, 2, 4], # [person, bicycle, motorbike]
        #     "roadside-objects": [10, 11, 13, 14] # [traffic light, fire hydrant, parking meter, bench]
        # }

        detected_frames_lst = []
        # Get the valid bounding boxes.
        for bb in boundingboxes.getBoundingBoxes():
            # [imageName, class, confidence, (bb coordinates XYX2Y2)]
            imageName = bb.getImageName()
            if imageName not in bb_image_gt:
                bb_image_gt[imageName] = []
            if imageName not in bb_image_det:
                bb_image_det[imageName] = []
            # print(f"Imagename: {imageName}")
            if bb.getBBType() == BBType.GroundTruth:
                if bb.getClassId() in classes and bb.getConfidence() >= confidence_gt:
                    bb_image_gt[imageName].append(
                        [
                            bb.getClassId(),
                            bb.getConfidence(),
                            bb.getAbsoluteBoundingBox(BBFormat.XYX2Y2)
                        ])
            else:
                if imageName not in detected_frames_lst:
                    detected_frames_lst.append(imageName)
                if bb.getClassId() in classes and bb.getConfidence() >= confidence_det:
                    bb_image_det[imageName].append([
                        bb.getClassId(),
                        bb.getConfidence(),
                        bb.getAbsoluteBoundingBox(BBFormat.XYX2Y2)
                    ])

        missed_frames_gt = 0
        for key, value in bb_image_gt.items():
            if len(value) == 0:
                missed_frames_gt += 1
        missed_frames_det = 0
        for key, value in bb_image_det.items():
            if len(value) == 0:
                missed_frames_det += 1
        # print(
        #    f"Some stats: total gt {len(bb_image_gt)}, total det {len(bb_image_det)}")
        # print(
        #    f"Some stats: missed gt {missed_frames_gt}, missed det {missed_frames_det}")

        # Total F1 score
        tp, fp, fn, count, precision, recall, f1 = _evaluate(
            bb_image_gt, bb_image_det)
        total_ret = {
            'total TP': tp,
            'total FP': fp,
            'total FN': fn,
            'total COUNT': count,
            'precision': precision,
            'recall': recall,
            'F1': f1
        }

        # Only F1 score of detected frames
        detected_bb_image_gt = {}
        detected_bb_image_det = {}
        for imageName in bb_image_gt.keys():
            if imageName in detected_frames_lst:
                detected_bb_image_gt[imageName] = bb_image_gt[imageName]
                detected_bb_image_det[imageName] = bb_image_det[imageName]

        tp, fp, fn, count, precision, recall, f1 = _evaluate(
            detected_bb_image_gt, detected_bb_image_det)
        detected_ret = {
            'total TP': tp,
            'total FP': fp,
            'total FN': fn,
            'total COUNT': count,
            'precision': precision,
            'recall': recall,
            'F1': f1
        }

        ret = {"All Frames F1": total_ret, "Detected Frames F1": detected_ret,
               "Stats": {"Total Frames": len(bb_image_gt), "Detected Frames": len(detected_frames_lst)}}
        return ret

    def GetRelativeMetrics_mAP(self, boundingboxes, confidence_gt=0.20, confidence_det=0.20, iou_threshold=0.5):
        '''
        Output: The performance mAP metrics relative to the ground truth obtained through a highly accurate model.
        '''
        def _evaluate(groundTruths, detections, classes):
            ret = []
            classes = sorted(classes)
            # Precision x Recall is obtained individually by each class
            # Loop through by classes
            for c in classes:
                # Get only detection of class c
                dects = []
                [dects.append(d) for d in detections if d[1] == c]
                # Get only ground truths of class c, use filename as key
                gts = {}
                npos = 0
                for g in groundTruths:
                    if g[1] == c:
                        npos += 1
                        gts[g[0]] = gts.get(g[0], []) + [g]

                # sort detections by decreasing confidence
                dects = sorted(dects, key=lambda conf: conf[2], reverse=True)
                TP = np.zeros(len(dects))
                FP = np.zeros(len(dects))
                # create dictionary with amount of gts for each image
                det = {key: np.zeros(len(gts[key])) for key in gts}

                # print("Evaluating class: %s (%d detections)" % (str(c), len(dects)))
                # Loop through detections
                for d in range(len(dects)):
                    # print('dect %s => %s' % (dects[d][0], dects[d][3],))
                    # Find ground truth image
                    gt = gts[dects[d][0]] if dects[d][0] in gts else []
                    iouMax = sys.float_info.min
                    for j in range(len(gt)):
                        # print('Ground truth gt => %s' % (gt[j][3],))
                        iou = Evaluator.iou(dects[d][3], gt[j][3])
                        if iou > iouMax:
                            iouMax = iou
                            jmax = j
                    # Assign detection as true positive/don't care/false positive
                    if iouMax >= iou_threshold:
                        if det[dects[d][0]][jmax] == 0:
                            TP[d] = 1  # count as true positive
                            # flag as already 'seen'
                            det[dects[d][0]][jmax] = 1
                            # print("TP")
                        else:
                            FP[d] = 1  # count as false positive
                            # print("FP")
                    # - A detected "cat" is overlaped with a GT "cat" with IOU >= IOUThreshold.
                    else:
                        FP[d] = 1  # count as false positive
                        # print("FP")
                # compute precision, recall and average precision
                acc_FP = np.cumsum(FP)
                acc_TP = np.cumsum(TP)
                rec = acc_TP / npos
                prec = np.divide(acc_TP, (acc_FP + acc_TP))
                # Depending on the method, call the right implementation
                # if method == MethodAveragePrecision.EveryPointInterpolation:
                [ap, mpre, mrec, ii] = Evaluator.CalculateAveragePrecision(
                    rec, prec)
                # else:
                #     [ap, mpre, mrec, _] = Evaluator.ElevenPointInterpolatedAP(
                #         rec, prec)
                # add class result in the dictionary to be returned
                r = {
                    'class': c,
                    # 'precision': prec,
                    # 'recall': rec,
                    'AP': ap,
                    # 'interpolated precision': mpre,
                    # 'interpolated recall': mrec,
                    'total positives': npos,
                    'total TP': np.sum(TP),
                    'total FP': np.sum(FP)
                }
                ret.append(r)
                # print(r)
            return ret

        # Seperate bounding boxes per image (frame)
        bb_image_gt = {}
        bb_image_det = {}
        # Check the class categories and labels here.
        # https://tech.amikelive.com/node-718/what-object-categories-labels-are-in-coco-dataset/
        # [car, bus, motorcycle, truck]. This is for DDS trafic videos
        classes = ['3', '6', '4', '8']

        # [person, chair, dining table]. This is for PKUMMD dataset videos
        # classes = ['1', '62', '67']
        # classes = {
        #     "vehicle": [3, 6, 7, 8], # [car, bus, train, truck]
        #     "persons": [1, 2, 4], # [person, bicycle, motorbike]
        #     "roadside-objects": [10, 11, 13, 14] # [traffic light, fire hydrant, parking meter, bench]
        # }

        # Get the valid bounding boxes.
        for bb in boundingboxes.getBoundingBoxes():
            # [imageName, class, confidence, (bb coordinates XYX2Y2)]
            imageName = bb.getImageName()

            if bb.getBBType() == BBType.GroundTruth:
                if imageName not in bb_image_gt:
                    bb_image_gt[imageName] = []
                if bb.getClassId() in classes and bb.getConfidence() >= confidence_gt:
                    bb_image_gt[imageName].append(
                        [
                            bb.getImageName(),
                            bb.getClassId(),
                            # bb.getConfidence(),
                            1,
                            bb.getAbsoluteBoundingBox(BBFormat.XYX2Y2)
                        ])
            else:
                if imageName not in bb_image_det:
                    bb_image_det[imageName] = []
                if bb.getClassId() in classes and bb.getConfidence() >= confidence_det:
                    bb_image_det[imageName].append([
                        bb.getImageName(),
                        bb.getClassId(),
                        bb.getConfidence(),
                        bb.getAbsoluteBoundingBox(BBFormat.XYX2Y2)
                    ])

        detections = []
        groundTruths = []
        ''' We use absence of bbox as a proxy to identify the missed frames.
            This is good for datasets for which there will be atleast one bbox
            in the non-missed frames. True for vehicle detection.
        '''
        for imageName in bb_image_det:
            groundTruths.extend(bb_image_gt[imageName])
            detections.extend(bb_image_det[imageName])
        # for imageName in bb_image_gt:
        #    groundTruths.extend(bb_image_gt[imageName])

        # print(f"Total images detected {len(bb_image_det)}")

        ret = _evaluate(
            groundTruths, detections, classes)

        mAP = 0
        for class_ap in ret:
            mAP += class_ap["AP"]
        assert len(ret) == len(classes)
        mAP = mAP / len(ret)
        ret.append({"mAP": mAP, "classes": len(ret)})
        # ret = {
        #     'total TP': tp,
        #     'total FP': fp,
        #     'total FN': fn,
        #     'total COUNT': count,
        #     'precision': precision,
        #     'recall': recall,
        #     'F1': f1
        # }

        return ret
